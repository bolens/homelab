import type { AuthLoginBody } from '@asking-ng/contracts/auth';
import type { AppRequest, AppResponse } from '../../types/http';
import { jsonError } from '../../lib/jsonError';
import { presentAuthSuccess } from './auth.presenter';
import { loginUser } from './auth.service';

export async function loginHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const { homelab-user, password } = req.body as AuthLoginBody;
  const result = await loginUser({ homelab-user, password });

  if (result.kind === 'invalid_credentials') {
    jsonError(res, req, 401, 'UNAUTHORIZED', 'Invalid credentials');
    return;
  }
  if (result.kind === 'account_disabled') {
    jsonError(res, req, 403, 'ACCOUNT_DISABLED', 'Account is suspended.');
    return;
  }

  res.json(presentAuthSuccess(result));
}
