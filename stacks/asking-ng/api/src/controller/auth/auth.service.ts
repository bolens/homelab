import { getSignupsEnabled } from '../../lib/appSettings';
import { ensureDefaultWorkspaceForUser } from '../../lib/workspaceBootstrap';
import { comparePassword, generateToken, hashPassword } from '../../utils/auth';
import { createUserRecord, findUserByUsername } from './auth.repository';

export type RegisterResult =
  | { kind: 'signups_disabled' }
  | {
      kind: 'ok';
      user: {
        id: number;
        homelab-user: string;
        role: string;
      };
      token: string;
    };

export async function registerUser(args: {
  homelab-user: string;
  password: string;
}): Promise<RegisterResult> {
  if (!(await getSignupsEnabled())) return { kind: 'signups_disabled' };

  const user = await createUserRecord({
    homelab-user: args.homelab-user,
    password: hashPassword(args.password),
    role: 'user',
  });
  await ensureDefaultWorkspaceForUser(user);

  return {
    kind: 'ok',
    user: {
      id: user.get('id') as number,
      homelab-user: user.get('homelab-user') as string,
      role: user.get('role') as string,
    },
    token: generateToken({
      id: user.get('id') as number,
      homelab-user: user.get('homelab-user') as string,
      role: user.get('role') as string,
    }),
  };
}

export type LoginResult =
  | { kind: 'invalid_credentials' }
  | { kind: 'account_disabled' }
  | {
      kind: 'ok';
      user: {
        id: number;
        homelab-user: string;
        role: string;
      };
      token: string;
    };

export async function loginUser(args: {
  homelab-user: string;
  password: string;
}): Promise<LoginResult> {
  const user = await findUserByUsername(args.homelab-user);
  if (!user || !comparePassword(args.password, user.get('password') as string)) {
    return { kind: 'invalid_credentials' };
  }
  if (!user.get('active')) return { kind: 'account_disabled' };

  return {
    kind: 'ok',
    user: {
      id: user.get('id') as number,
      homelab-user: user.get('homelab-user') as string,
      role: user.get('role') as string,
    },
    token: generateToken({
      id: user.get('id') as number,
      homelab-user: user.get('homelab-user') as string,
      role: user.get('role') as string,
    }),
  };
}
