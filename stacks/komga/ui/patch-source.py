"""Checked patch for Komga 1.28.1's next UI notification presentation."""
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1])
source = root / 'src/composables/sse.ts'
text = source.read_text()
replacements = {
    "import { ApiBaseUrl } from '@/api/base'": "import { ApiBaseUrl } from '@/api/base'\nimport { komgaGetBookById } from '@/generated/openapi'\nimport { importFilename, resolveImportTitle } from '@/utils/import-title'",
    'watch(localEvent, (newEvent) => {': 'watch(localEvent, async (newEvent) => {',
    'message: event.data.sourceFile,': "message: await resolveImportTitle(event.data, (bookId, signal) =>\n              komgaGetBookById({ path: { bookId }, signal })),",
    '${event.data.sourceFile}`': '${importFilename(event.data.sourceFile)}`',
}
for old, new in replacements.items():
    if text.count(old) != 1:
        raise SystemExit('Upstream notification contract changed: ' + old)
    text = text.replace(old, new)
source.write_text(text)
shutil.copy2(Path(__file__).with_name('import-title.ts'), root / 'src/utils/import-title.ts')
