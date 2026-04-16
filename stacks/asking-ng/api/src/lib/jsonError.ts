import type { AppRequest, AppResponse } from '../types/http';

/** Consistent JSON error shape (matches {@link errorHandler} for `HttpError`). */
export function jsonError(
  res: AppResponse,
  req: AppRequest,
  statusCode: number,
  code: string,
  message: string,
  details?: unknown,
): void {
  res.status(statusCode).json({
    error: {
      code,
      message,
      ...(details !== undefined ? { details } : {}),
    },
    requestId: req.requestId,
  });
}
