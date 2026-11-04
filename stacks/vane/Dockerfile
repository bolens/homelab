FROM itzcrazykns1337/vane:latest@sha256:0b61bf0d4470e9f2a9c71f794b72fab6e5a612177172770684c158a461f6896e AS patched

COPY patch-openai-stream.cjs test-openai-stream.cjs /tmp/vane-patch/
RUN node /tmp/vane-patch/test-openai-stream.cjs /home/vane \
    && node /tmp/vane-patch/patch-openai-stream.cjs /home/vane

FROM itzcrazykns1337/vane:latest@sha256:0b61bf0d4470e9f2a9c71f794b72fab6e5a612177172770684c158a461f6896e
COPY --from=patched /home/vane/.next/server/chunks/136.js /home/vane/.next/server/chunks/136.js
