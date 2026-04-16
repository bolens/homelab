type UserSummary = {
  id: number;
  homelab-user: string;
  role: string;
};

export function presentUserSummary(user: UserSummary): UserSummary {
  return {
    id: user.id,
    homelab-user: user.homelab-user,
    role: user.role,
  };
}

export function presentUsersList(payload: { users: UserSummary[] }): Record<string, unknown> {
  return { users: payload.users.map((user) => presentUserSummary(user)) };
}

export function presentUser(payload: { user: UserSummary }): Record<string, unknown> {
  return { user: presentUserSummary(payload.user) };
}

export function presentDeletedUserMessage(id: number): Record<string, unknown> {
  return { message: `User ${id} deleted` };
}

export function presentPasswordResetMessage(): Record<string, unknown> {
  return { message: 'Password reset' };
}
