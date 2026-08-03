#!/bin/sh
# Run before upstream start.sh. Official image only rewrites BUILT_NEXT_PUBLIC_WEBAPP_URL
# (baked localhost) → NEXT_PUBLIC_WEBAPP_URL. If the container ever ran with another public
# URL, that string remains in apps/web/.next until explicitly replaced — SSR and client
# chunks can still show the old hostname after you change stack.env.
set -e
cd /calcom

if [ -n "$CALCOM_REPLACE_OLD_PUBLIC_URL" ] && [ "$CALCOM_REPLACE_OLD_PUBLIC_URL" != "$NEXT_PUBLIC_WEBAPP_URL" ]; then
	echo "calcom homelab: replacing stale public URL in .next (${CALCOM_REPLACE_OLD_PUBLIC_URL} → ${NEXT_PUBLIC_WEBAPP_URL})"
	scripts/replace-placeholder.sh "$CALCOM_REPLACE_OLD_PUBLIC_URL" "$NEXT_PUBLIC_WEBAPP_URL" || true
	case "$CALCOM_REPLACE_OLD_PUBLIC_URL" in
	https://*)
		OLD_HTTP=$(printf '%s' "$CALCOM_REPLACE_OLD_PUBLIC_URL" | sed 's|^https://|http://|')
		NEW_HTTP=$(printf '%s' "$NEXT_PUBLIC_WEBAPP_URL" | sed 's|^https://|http://|')
		if [ "$OLD_HTTP" != "$CALCOM_REPLACE_OLD_PUBLIC_URL" ]; then
			scripts/replace-placeholder.sh "$OLD_HTTP" "$NEW_HTTP" || true
		fi
		;;
	esac
fi

exec /calcom/scripts/start.sh
