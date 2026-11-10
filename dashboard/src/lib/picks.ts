/**
 * Photos chosen in several picks, from as many folders as needed (the lab's machines plan, tool
 * gap 6). A browser's file picker opens one folder at a time, so each pick adds to the photos
 * already chosen. The agent's T33901 job had five photos because one pick could reach only one
 * folder, where v8 had 24 (drill-press report, section 7.3, item 6).
 */

/** What a picked file is told apart by: the browser gives no path. */
export interface PickedFile {
  name: string
  size: number
  lastModified: number
}

/** The same name, size and time: the same file picked again. */
export function fileKey(file: PickedFile): string {
  return `${file.name}|${file.size}|${file.lastModified}`
}

/** The picked files that are not chosen yet, in their order, each once. */
export function newPicks<F extends PickedFile>(
  chosen: readonly PickedFile[],
  picked: readonly F[],
): { added: F[]; repeated: string[] } {
  const seen = new Set(chosen.map(fileKey))
  const added: F[] = []
  const repeated: string[] = []
  for (const file of picked) {
    const key = fileKey(file)
    if (seen.has(key)) {
      repeated.push(file.name)
    } else {
      seen.add(key)
      added.push(file)
    }
  }
  return { added, repeated }
}
