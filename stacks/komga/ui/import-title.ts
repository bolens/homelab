/** Display-only labels. Never modify import paths or catalog metadata. */
type ImportedBook = {
  seriesTitle?: string
  oneshot?: boolean
  metadata?: { number?: string; title?: string; releaseDate?: Date | string }
}

function issueNumber(value: string): string {
  return value.replace(/^0+(?=\d)/, '')
}

export function importFilename(value: string): string {
  const leaf = value.replace(/\\/g, '/').split('/').pop() || ''
  const stem = leaf.replace(/\.(?:cbz|cbr|cb7|cbt|pdf|epub|zip|rar|7z)$/i, '')
    .replace(/\[__\d+__\]/g, '').trim()
  // Release tags after a publication year are not part of the comic title.
  const issue = stem.match(/^(.*?)\s+(\d+(?:\.\d+)?[a-z]?)\s*\(((?:19|20)\d{2})\)(?:\s*\([^)]*\))*$/i)
  if (issue?.[1] && issue[2] && issue[3]) return `${issue[1]} #${issueNumber(issue[2])} (${issue[3]})`
  return stem || 'Imported book'
}

export function importBookTitle(book: ImportedBook | undefined, source: string): string {
  const series = book?.seriesTitle?.trim()
  const metadata = book?.metadata
  const number = metadata?.number?.trim()
  const title = metadata?.title?.trim()
  // Catalog series/number avoids release-group suffixes in default book titles.
  if (series && number && !book?.oneshot) {
    const date = metadata?.releaseDate
    const year = date instanceof Date ? String(date.getUTCFullYear()) : date?.match(/^(\d{4})-/)?.[1]
    return `${series} #${issueNumber(number)}${year && /^\d{4}$/.test(year) ? ` (${year})` : ''}`
  }
  if (title) return title
  if (series) return series
  return importFilename(source)
}

export async function resolveImportTitle(
  event: { bookId?: string | null; sourceFile: string },
  getBook: (id: string, signal: AbortSignal) => Promise<ImportedBook | undefined>,
): Promise<string> {
  if (event.bookId) {
    try {
      return importBookTitle(await getBook(event.bookId, AbortSignal.timeout(1500)), event.sourceFile)
    } catch {
      // Import succeeded even when metadata is unavailable, forbidden or timed out.
    }
  }
  return importFilename(event.sourceFile)
}
