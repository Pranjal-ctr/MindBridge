#!/bin/sh
# Substitute the API origin into the Content-Security-Policy at container start.
#
# The policy has to name the exact origin the browser may call. That origin is
# only known at deploy time, and it is the same value the bundle was built
# with, so it is passed through as an environment variable rather than baked
# into the image -- one image can then serve staging and production.
#
# A CSP that omits the API origin fails in the worst possible way: requests are
# blocked by the browser before they are sent, so the server logs are empty and
# the page simply does nothing. Hence the explicit failure below.
set -eu

CONF=/etc/nginx/conf.d/default.conf

if [ -z "${API_ORIGIN:-}" ]; then
    echo "ERROR: API_ORIGIN is required (e.g. https://api.kio.example)." >&2
    echo "       Without it the CSP would block every API call silently." >&2
    exit 1
fi

# Origin only: a CSP source may not contain a path.
case "$API_ORIGIN" in
    http://*|https://*) ;;
    *) echo "ERROR: API_ORIGIN must include the scheme, e.g. https://api.kio.example" >&2; exit 1 ;;
esac

sed -i "s|__API_ORIGIN__|${API_ORIGIN}|g" "$CONF"
echo "==> CSP connect-src permits ${API_ORIGIN}"

exec "$@"
