"""Offline checks against the actual installed GHunt and its dependency graph."""
import asyncio
from contextlib import redirect_stdout
from importlib.metadata import version
import io
import json
import unittest

from alive_progress import alive_bar
from alive_progress.utils.cells import split_graphemes
from ghunt.helpers.utils import get_httpx_client, get_url_image_flathash, oprint
from ghunt.lib.httpx import AsyncClient
from ghunt.objects.base import Position
import httpx
from PIL import Image


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_reviewed_installed_versions(self):
        expected = {"ghunt": "2.3.4+homelab.1", "alive-progress": "3.3.0+homelab.1",
                    "httpx": "0.28.1", "jsonpickle": "4.1.2",
                    "graphemeu": "0.11.0", "pillow": "13.0.0"}
        for name, wanted in expected.items():
            self.assertEqual(version(name), wanted)

    def test_real_client_factory_and_proxy_construction(self):
        async def run():
            async with get_httpx_client() as client:
                self.assertEqual(client.timeout.read, 15)
            async with AsyncClient(proxy="http://127.0.0.1:3128", trust_env=False):
                pass
        asyncio.run(run())

    def test_per_request_cookie_isolation_and_json(self):
        seen = []
        def reply(request):
            seen.append(request.headers.get("cookie"))
            return httpx.Response(200, json={"ok": True}, headers={"set-cookie": "server=value"})
        async def run():
            async with AsyncClient(transport=httpx.MockTransport(reply), trust_env=False) as client:
                response = await client.get("https://example.invalid/", cookies={"request": "one"})
                self.assertEqual(response.json(), {"ok": True})
                await client.get("https://example.invalid/")
        asyncio.run(run())
        self.assertEqual(seen, ["request=one", None])

    def test_json_export_of_actual_slotted_ghunt_object(self):
        position = Position()
        position.latitude = 12.5
        position.longitude = -45.25
        output = io.StringIO()
        with redirect_stdout(output):
            oprint({"position": position, "title": "Cafe\u0301", "missing": None})
        data = json.loads(output.getvalue())
        self.assertEqual(data["title"], "Cafe\u0301")
        self.assertIsNone(data["missing"])
        self.assertEqual(data["position"]["latitude"], 12.5)
        self.assertEqual(data["position"]["longitude"], -45.25)

    def test_unicode_progress_rendering(self):
        text = "e\u0301👩🏽‍💻🇺🇳"
        self.assertEqual(split_graphemes(text), ("e\u0301", "👩🏽‍💻", "🇺🇳"))
        output = io.StringIO()
        with alive_bar(2, title=text, file=output, force_tty=False) as bar:
            bar()
            bar()
        self.assertIn("2/2", output.getvalue())
        self.assertIn(text, output.getvalue())

    def test_pillow_jpeg_tiff_and_actual_ghunt_image_hash(self):
        async def run():
            for format_name in ("JPEG", "TIFF"):
                image = Image.new("RGB", (16, 16), "white")
                image.putpixel((0, 0), (0, 0, 0))
                encoded = io.BytesIO()
                image.save(encoded, format=format_name)
                def reply(request):
                    return httpx.Response(200, content=encoded.getvalue())
                async with AsyncClient(transport=httpx.MockTransport(reply)) as client:
                    digest = await get_url_image_flathash(client, "https://example.invalid/image")
                self.assertEqual(len(digest), 16)
                self.assertNotEqual(digest, "0000000000000000")
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
