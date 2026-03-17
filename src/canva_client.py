from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Protocol
import base64

from .canva_oauth import TokenStore, get_valid_access_token
from .models import AssetPlan, RuntimeSettings, TemplateMap
from .renderer import render_mock_asset


def _guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def _name_base64(name: str) -> str:
    trimmed = name[:50]
    return base64.b64encode(trimmed.encode("utf-8")).decode("ascii")


def _build_autofill_payload(plan: AssetPlan, template_map: TemplateMap, image_asset_ref: str) -> dict[str, Any]:
    return {
        "brand_template_id": template_map.template_id,
        "data": {
            template_map.fields["background_image"]: {
                "asset_id": image_asset_ref,
            },
            template_map.fields["header_text"]: plan.hook.text,
            template_map.fields["subtitle_text"]: plan.subtitle.text,
        },
        "title": plan.asset_id,
    }


class CanvaClient(Protocol):
    def render_asset(self, plan: AssetPlan, template_map: TemplateMap, outputs_dir: Path, force: bool) -> tuple[Path, Path]:
        ...


class MockCanvaClient:
    def render_asset(self, plan: AssetPlan, template_map: TemplateMap, outputs_dir: Path, force: bool) -> tuple[Path, Path]:
        return render_mock_asset(plan, template_map, outputs_dir, force)


class LiveCanvaClient:
    def __init__(self, token_store: TokenStore, template_id: str) -> None:
        self.token_store = token_store
        self.template_id = template_id
        self.base_url = "https://api.canva.com/rest/v1"

    def render_asset(self, plan: AssetPlan, template_map: TemplateMap, outputs_dir: Path, force: bool) -> tuple[Path, Path]:
        import requests

        export_path = outputs_dir / f"{plan.asset_id}.mp4"
        thumbnail_path = outputs_dir / f"{plan.asset_id}.jpg"
        manifest_path = outputs_dir / f"{plan.asset_id}.canva.json"
        if export_path.exists() and thumbnail_path.exists() and manifest_path.exists() and not force:
            return export_path, thumbnail_path

        access_token = get_valid_access_token(self.token_store)
        image_asset_id = self._upload_image_asset(access_token, plan)
        design_id = self._create_and_wait_for_autofill(access_token, plan, template_map, image_asset_id)
        download_url = self._create_and_wait_for_export(access_token, design_id)

        media = requests.get(download_url, timeout=120)
        media.raise_for_status()
        outputs_dir.mkdir(parents=True, exist_ok=True)
        export_path.write_bytes(media.content)

        # Keep thumbnail generation local until the Canva thumbnail flow is needed.
        _, thumbnail_path = render_mock_asset(plan, template_map, outputs_dir, force=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "asset_id": plan.asset_id,
                    "brand_template_id": template_map.template_id,
                    "design_id": design_id,
                    "image_asset_id": image_asset_id,
                    "download_url": download_url,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return export_path, thumbnail_path

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    def _upload_image_asset(self, access_token: str, plan: AssetPlan) -> str:
        import requests

        image_bytes = plan.image_path.read_bytes()
        create_response = requests.post(
            f"{self.base_url}/asset-uploads",
            headers={
                **self._headers(access_token),
                "Content-Type": "application/octet-stream",
                "Asset-Upload-Metadata": json.dumps({"name_base64": _name_base64(plan.image_path.name)}),
            },
            data=image_bytes,
            timeout=30,
        )
        if not create_response.ok:
            raise RuntimeError(
                f"Canva asset upload failed ({create_response.status_code}): {create_response.text[:1000]}"
            )
        payload = create_response.json()
        job = payload.get("job", {})
        job_id = job.get("id") or payload.get("id")
        if not job_id:
            raise RuntimeError(f"Canva asset upload job did not return an id: {payload}")
        return self._wait_for_asset_upload(access_token, job_id)

    def _wait_for_asset_upload(self, access_token: str, job_id: str, max_attempts: int = 8) -> str:
        import requests

        for attempt in range(max_attempts):
            response = requests.get(
                f"{self.base_url}/asset-uploads/{job_id}",
                headers=self._headers(access_token),
                timeout=30,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Canva asset upload poll failed ({response.status_code}): {response.text[:1000]}"
                )
            payload = response.json()
            job = payload.get("job", {})
            status = job.get("status")
            if status == "success":
                asset = job.get("asset") or payload.get("asset") or {}
                asset_id = asset.get("id")
                if not asset_id:
                    raise RuntimeError(f"Canva asset upload completed without an asset id: {payload}")
                return asset_id
            if status == "failed":
                raise RuntimeError(f"Canva asset upload failed: {job.get('error') or payload}")
            time.sleep(min(2 ** attempt, 15))
        raise TimeoutError("Timed out waiting for Canva asset upload")

    def _create_and_wait_for_autofill(
        self,
        access_token: str,
        plan: AssetPlan,
        template_map: TemplateMap,
        image_asset_id: str,
        max_attempts: int = 8,
    ) -> str:
        import requests

        response = requests.post(
            f"{self.base_url}/autofills",
            headers={**self._headers(access_token), "Content-Type": "application/json"},
            json=_build_autofill_payload(plan, template_map, image_asset_id),
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"Canva autofill failed ({response.status_code}): {response.text[:1000]}")
        payload = response.json()
        job = payload.get("job", {})
        job_id = job.get("id") or payload.get("id")
        if not job_id:
            raise RuntimeError(f"Canva autofill job did not return an id: {payload}")

        for attempt in range(max_attempts):
            poll = requests.get(
                f"{self.base_url}/autofills/{job_id}",
                headers=self._headers(access_token),
                timeout=30,
            )
            if not poll.ok:
                raise RuntimeError(f"Canva autofill poll failed ({poll.status_code}): {poll.text[:1000]}")
            poll_payload = poll.json()
            poll_job = poll_payload.get("job", {})
            status = poll_job.get("status")
            if status == "success":
                result = poll_job.get("result") or poll_payload.get("result") or {}
                design_id = result.get("design_id") or result.get("id")
                if not design_id:
                    raise RuntimeError(f"Canva autofill completed without a design id: {poll_payload}")
                return design_id
            if status == "failed":
                raise RuntimeError(f"Canva autofill failed: {poll_job.get('error') or poll_payload}")
            time.sleep(min(2 ** attempt, 15))
        raise TimeoutError("Timed out waiting for Canva autofill job")

    def _create_and_wait_for_export(self, access_token: str, design_id: str, max_attempts: int = 8) -> str:
        import requests

        response = requests.post(
            f"{self.base_url}/exports",
            headers={**self._headers(access_token), "Content-Type": "application/json"},
            json={
                "design_id": design_id,
                "format": {"type": "mp4"},
            },
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"Canva export failed ({response.status_code}): {response.text[:1000]}")
        payload = response.json()
        job = payload.get("job", {})
        job_id = job.get("id") or payload.get("id")
        if not job_id:
            raise RuntimeError(f"Canva export job did not return an id: {payload}")

        for attempt in range(max_attempts):
            poll = requests.get(
                f"{self.base_url}/exports/{job_id}",
                headers=self._headers(access_token),
                timeout=30,
            )
            if not poll.ok:
                raise RuntimeError(f"Canva export poll failed ({poll.status_code}): {poll.text[:1000]}")
            poll_payload = poll.json()
            poll_job = poll_payload.get("job", {})
            status = poll_job.get("status")
            if status == "success":
                urls = poll_job.get("urls") or []
                download_url = urls[0] if urls else None
                if not download_url:
                    raise RuntimeError(f"Canva export completed without a download URL: {poll_payload}")
                return download_url
            if status == "failed":
                raise RuntimeError(f"Canva export failed: {poll_job.get('error') or poll_payload}")
            time.sleep(min(2 ** attempt, 15))
        raise TimeoutError("Timed out waiting for Canva export job")


def build_canva_client(settings: RuntimeSettings, template_map: TemplateMap) -> CanvaClient:
    if settings.canva_mode == "live":
        import os

        template_id = os.getenv("CANVA_TEMPLATE_ID", template_map.template_id).strip()
        if not template_id or template_id == "CANVA_TEMPLATE_ID":
            raise RuntimeError("CANVA_MODE=live requires CANVA_TEMPLATE_ID")
        return LiveCanvaClient(token_store=TokenStore(settings.state_dir), template_id=template_id)
    return MockCanvaClient()
