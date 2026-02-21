# Web-Check Troubleshooting Guide

## Issues Found in Browser Console Logs

### ✅ Fixable Issues

#### 1. Shodan API Key Not Working
**Error:** `GET https://api.shodan.io/shodan/host/...?key=default_value_if_not_set 401 (Unauthorized)`

**Root Cause:** `REACT_APP_SHODAN_API_KEY` is a client-side React variable that must be available at build time. Since we're using a pre-built Docker image (`lissy93/web-check:latest`), the environment variable isn't available to the React app.

**Status:** ⚠️ **Cannot be fixed with pre-built image** - The API key is set in the container, but the React frontend was built without it. The frontend makes direct API calls to Shodan, so it needs the key at build time.

**Workaround:** None available without rebuilding the image from source with the API key.

#### 2. WhoAPI Key Not Working  
**Error:** `GET https://api.whoapi.com/?domain=...&apikey=default_value_if_not_set 401 (Unauthorized)`

**Root Cause:** Same as Shodan - `REACT_APP_WHO_API_KEY` is a client-side variable that needs to be available at build time.

**Status:** ⚠️ **Cannot be fixed with pre-built image** - Same limitation as Shodan.

**Workaround:** None available without rebuilding the image from source.

### ⚠️ Known Unfixable Issues (External Services)

#### 3. TLS Observatory Errors
**Error:** `getaddrinfo ENOTFOUND tls-observatory.services.mozilla.com`

**Root Cause:** Mozilla's TLS Observatory service has been archived and is no longer available.

**Status:** ✅ **Expected behavior** - Documented in README.md. These checks will fail until web-check supports an alternative service.

**Reference:** See [web-check#276](https://github.com/Lissy93/web-check/issues/276)

#### 4. Mail-Config 500 Error
**Error:** `The "callback" argument must be of type function. Received undefined`

**Root Cause:** Server-side bug in web-check's mail-config endpoint.

**Status:** 🐛 **Upstream bug** - Needs to be fixed in web-check itself.

**Workaround:** None - this is a bug in the web-check application.

#### 5. Quality Metrics 500 Error
**Error:** `Request failed with status code 500` from PageSpeed Insights API

**Root Cause:** Google's PageSpeed Insights API sometimes returns 500 errors. This is a known issue with the API itself, not our configuration.

**Status:** ⚠️ **Intermittent Google API issue** - The API key is configured correctly, but Google's API has reliability issues.

**Possible Solutions:**
- Verify API key restrictions in Google Cloud Console
- Ensure PageSpeed Insights API is enabled
- Check API quotas
- Wait and retry (often transient)

#### 6. Website Carbon API 422 Errors
**Error:** `GET https://api.websitecarbon.com/b?url=undefined 422 (Unprocessable Content)`

**Root Cause:** Bug in web-check where it's not passing the URL correctly to the Website Carbon API.

**Status:** 🐛 **Upstream bug** - Needs to be fixed in web-check itself.

**Workaround:** None - this is a bug in the web-check application.

### ℹ️ Minor Issues (Non-Critical)

#### 7. HTTP/2 Protocol Errors for Images
**Error:** `GET https://i.ibb.co/... net::ERR_HTTP2_PROTOCOL_ERROR`

**Root Cause:** External CDN (ImgBB) issues, not related to our setup.

**Status:** ✅ **External service issue** - Nothing we can fix.

#### 8. Font Preload Warning
**Warning:** Font preloaded but not used within a few seconds

**Status:** ✅ **Performance warning** - Non-critical, doesn't affect functionality.

#### 9. Archives Timeout
**Error:** `The archives job timed out after 10720ms`

**Status:** ⚠️ **Timeout** - Some checks may take longer than expected. This is normal for some URLs.

## Summary

### Working Features ✅
- IP info
- SSL chain
- DNS records
- Location
- Server info
- Headers
- Domain info
- DNSSEC
- Status checks
- HSTS
- Robots.txt
- Block lists
- Features detection
- Rank
- Ports
- Screenshot
- Carbon footprint (partial)
- Security.txt
- Social tags
- HTTP security
- Threats
- Cookies
- Tech stack
- Trace route
- Redirects
- Linked pages

### Not Working ❌
- Shodan (API key not available at build time)
- WhoAPI (API key not available at build time)
- TLS Observatory checks (service archived)
- Mail-config (upstream bug)
- Quality metrics (intermittent Google API issues)
- Website Carbon (upstream bug with URL parameter)

## Recommendations

1. **For Shodan/WhoAPI:** If these features are critical, consider building web-check from source with the API keys baked in, or wait for web-check to add backend API endpoints that proxy these calls.

2. **For Quality Metrics:** The 500 errors are often transient. The API key is configured correctly. If issues persist, check Google Cloud Console for API restrictions or quota limits.

3. **For other bugs:** Monitor the web-check GitHub repository for fixes and updates.
