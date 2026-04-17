import type { AuthRegisterBody } from '@asking-ng/contracts/auth';
import { jsonError } from '../../lib/jsonError';
import type { AppRequest, AppResponse } from '../../types/http';
import { presentAuthSuccess } from './auth.presenter';
import { registerUser } from './auth.service';

export async function registerHandler(req: AppRequest, res: AppResponse): Promise<void> {
  const { homelab-user, password } = req.body as AuthRegisterBody;
  const result = await registerUser({ homelab-user, password });

  if (result.kind === 'signups_disabled') {
    jsonError(res, req, 403, 'SIGNUPS_DISABLED', 'New registrations are disabled.');
    return;
  }

  res.status(201).json(presentAuthSuccess(result));
}
