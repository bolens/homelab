import db from '../../connections';
import Poll from '../../model/Poll';

export async function findPollById(pollId: string) {
  return Poll.findByPk(pollId);
}

export async function findPollByVanitySlug(vanitySlug: string) {
  return Poll.findOne({ where: { vanitySlug } });
}

export async function createPollRow(payload: Record<string, unknown>) {
  await db.sync();
  return Poll.create(payload);
}
