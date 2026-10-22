"""Pin/guard regression checks; full apply test uses a pristine export when supplied."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("patch_source", HERE / "patch_source.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PatchTests(unittest.TestCase):
    def test_source_and_base_pins(self):
        dockerfile = (HERE / "Dockerfile").read_text()
        self.assertIn(module.SOURCE_SHA, dockerfile)
        self.assertIn("sha256:9ab54dfa133ca038992cea019490c951843712dcb66fec518a01f25d076ef335", dockerfile)
        self.assertIn('test "$(readlink /app/kavita/config)" = /config', dockerfile)
        self.assertIn("--chown=abc:abc", dockerfile)
        self.assertNotIn("ENTRYPOINT", dockerfile)

    def test_patch_rejects_incompatible_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((FileNotFoundError, ValueError)):
                module.patch(Path(directory))

    def test_capability_client_fails_closed_and_bounds_requests(self):
        client = (HERE / "IndependentProvider.cs").read_text()
        for fragment in ['AllowAutoRedirect = false', '262144', 'TimeSpan.FromSeconds(10)',
                         'protocolVersion', 'GetInt32() != 1', 'X-Provider-Key', 'Interlocked.CompareExchange',
                         'catch (Exception) { Cached = Unavailable; valid = false; }', 'plus.kavitareader.com']:
            self.assertIn(fragment, client)

    @unittest.skipUnless(os.environ.get("KAVITA_SOURCE_EXPORT"), "set KAVITA_SOURCE_EXPORT to pristine pinned export")
    def test_apply_full_patch_and_official_regression_guards(self):
        source = Path(os.environ["KAVITA_SOURCE_EXPORT"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            shutil.copytree(source, root, ignore=shutil.ignore_patterns("node_modules", "bin", "obj", ".git"))
            module.patch(root)
            license_source = (root / "Kavita.Services/Plus/LicenseService.cs").read_text()
            self.assertEqual(license_source.count("if (IndependentProvider.Enabled) return false;"), 2)
            self.assertIn("if (IndependentProvider.Enabled) return null;", license_source)
            self.assertIn('Configuration.KavitaPlusApiUrl + "/api/license/check"', license_source)
            headers = (root / "Kavita.Common/Extensions/FlurlExtensions.cs").read_text()
            self.assertIn('.WithHeader(Headers.LicenseKey, license)', headers)
            self.assertIn('s.Redirects.Enabled = false', headers)
            self.assertIn('uri.AbsolutePath.StartsWith("/api/license"', headers)
            basic = headers.split("public static IFlurlRequest WithBasicHeaders", 1)[1]
            self.assertNotIn("IndependentProvider", basic)
            authorization = (root / "Kavita.Server/Attributes/KPlusAttribute.cs").read_text()
            self.assertIn("!userContext.IsAuthenticated", authorization)
            self.assertIn("await licenseService.HasActiveLicense", authorization)
            scrobbling = (root / "Kavita.Services/Plus/ScrobblingService.cs").read_text()
            self.assertIn("if (!Kavita.Common.IndependentProvider.Enabled && string.IsNullOrEmpty(license.Value)) return true;", scrobbling)
            sync = scrobbling.split("// Unknown expiry is not evidence", 1)[1].split("// Official-mode behavior", 1)[0]
            self.assertNotIn("DateTime.MinValue", sync)
            self.assertNotIn("DateTime.MaxValue", sync)
            self.assertIn("if (!userInfo.IsSuccess || userInfo.Data == null) return", sync)
            self.assertIn("if (actualExpiry.HasValue)", sync)
            validation = scrobbling.split("private async Task<bool> ValidateUserToken", 1)[1].split("private async Task<bool> ValidateSeriesCanBeScrobbled", 1)[0]
            self.assertLess(validation.index("ValidateIndependentAccount"), validation.index("providerService.IsTokenValid"))
            cleanup = scrobbling.split("private async Task CleanupOldOrBuggedEvents()", 1)[1].split("#region", 1)[0]
            self.assertLess(cleanup.index("if (IndependentProvider.Enabled) return;"), cleanup.index("ScrobbleRepository.Remove"))
            controller = (root / "Kavita.Server/Controllers/ScrobblingController.cs").read_text()
            self.assertLess(controller.index("IndependentProvider.Enabled && string.IsNullOrEmpty(scrobbleProvider.AuthenticationToken)"), controller.index("ClearEventsForProvider"))
            self.assertIn("pending events will be retained", scrobbling)
            self.assertIn("no expired state is assumed", scrobbling)
            self.assertIn("TokenExpiryKnown = actualExpiry.HasValue", scrobbling)
            self.assertIn("IndependentProvider.CanQueueScrobbleEvents()", scrobbling)
            self.assertIn("IndependentProvider.KnownScrobbleAction((int)provider, (int)eventType)", scrobbling)
            self.assertIn("return await PostIndependentScrobbleUpdate(data, evt)", scrobbling)
            self.assertIn("Successful: true, ErrorMessage: null", scrobbling)
            independent_post = scrobbling.split("private async Task<int> PostIndependentScrobbleUpdate", 1)[1].split("private async Task<DateTime?> GetTokenExpiry", 1)[0]
            self.assertNotIn("SetErrorMessage", independent_post)
            self.assertIn("independent-delivery-unconfirmed", independent_post)
            self.assertIn("JsonSerializerDefaults.Web", headers)
            template = (root / "UI/Web/src/app/user-settings/manage-scrobble-providers/manage-scrobble-providers.component.html").read_text()
            self.assertIn("supportsScrobbleAction(provider, ScrobbleEventType.Review)", template)
            self.assertIn("supportsScrobbleAction(provider, ScrobbleEventType.ReadStatusUpdate)", template)
            self.assertIn("supportsReviewVisibility(provider, opt)", template)
            self.assertIn("independentLicense.independent() && opt === 3", template)
            scheduler = (root / "Kavita.Services/TaskScheduler.cs").read_text()
            self.assertIn('IndependentProvider.Has("oauth")', scheduler)
            self.assertIn('IndependentProvider.Has("scrobbling")', scheduler)
            self.assertIn('IndependentProvider.Has("metadata")', scheduler)
            self.assertIn('RecurringJob.RemoveIfExists(TaskSchedulerConstants.RefreshConnectedTokensId)', scheduler)
            stats = (root / "Kavita.Services/StatsService.cs").read_text()
            self.assertIn("dto.ActiveKavitaPlusSubscription = await _licenseService.HasActiveLicense();", stats)
            ui = (root / "UI/Web/src/app/_services/license.service.ts").read_text()
            self.assertIn("this._hasActiveLicense.set(res?.isActive || false)", ui)
            self.assertIn("hasFeatureAccess()", ui)
            self.assertNotIn("_hasActiveLicense.set(true)", ui)
            api = (root / "Kavita.Services/Plus/KavitaPlusApiService.cs").read_text()
            self.assertEqual(api.count("if (IndependentProvider.Enabled) return await IndependentRequest<"), 5)
            self.assertIn('.PostJsonAsync(payload, cancellationToken: ct).ReceiveJson<KPlusResult<T>>()', api)
            self.assertIn('.SetQueryParam("accessToken", token)', api)  # retained official branch
            safe_request = api.split("private async Task<KPlusResult<T>> IndependentRequest", 1)[1].split("private const string ScrobblingPath", 1)[0]
            self.assertNotIn("logger.LogError(ex", safe_request)
            oauth_service = (root / "Kavita.Services/Plus/OAuthService.cs").read_text()
            self.assertEqual(oauth_service.count("Kavita.Common.IndependentProvider.Enabled ? expiresIn : null"), 3)
            imports = (root / "Kavita.Services/Plus/WantToReadSyncService.cs").read_text()
            self.assertIn(": await unitOfWork.SeriesRepository.MatchSeriesAsync(unmatchedSeries, ct)", imports)
            exact = imports.split("private async Task<Kavita.Models.Entities.Series?> MatchIndependentSeries", 1)[1].split("public async Task Sync", 1)[0]
            self.assertNotIn("MatchSeriesAsync", exact)
            self.assertNotIn("external.Name", exact)
            self.assertNotIn("external.Synonyms", exact)
            self.assertIn("GetSeriesDtoByIdsAsync(ids, user, ct)", exact)
            self.assertIn("item.Provider != kv.Key", imports)
            self.assertIn("Take(1001)", exact)
            self.assertIn("chapter.HardcoverId == identity.Value", exact)
            oauth = (root / "Kavita.Server/Controllers/OAuthController.cs").read_text()
            self.assertIn("return await StartIndependentFlow(upstream)", oauth)
            self.assertIn('return BadRequest("Use the independent OAuth callback.")', oauth)
            independent = oauth.split("private async Task<IActionResult> StartIndependentFlow", 1)[1]
            self.assertNotIn("GetInstanceUrl", independent.split("private static string GetInstanceUrl", 1)[0])
            for boundary in ["browserBindingHash = hash", "browserBinding = browser", 'FromQuery(Name = "iss")',
                             "FixedTimeEquals", "_independentProtector.Unprotect", "SameSiteMode.Lax", "HttpOnly = true"]:
                self.assertIn(boundary, independent)
            self.assertIn("GetUserByAuthKey(binding.ApiKey", independent)
            self.assertNotIn("Redirect(token", independent)
            controller = (root / "Kavita.Server/Controllers/ProviderCapabilitiesController.cs").read_text()
            self.assertIn(": BaseApiController", controller)
            with self.assertRaises(ValueError):
                module.patch(root)


if __name__ == "__main__":
    unittest.main()
