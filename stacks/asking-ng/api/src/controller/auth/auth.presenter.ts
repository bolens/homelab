export function presentAuthSuccess(payload: {
  user: { id: number; homelab-user: string; role: string };
  token: string;
}): Record<string, unknown> {
  return {
    user: payload.user,
    token: payload.token,
  };
}
