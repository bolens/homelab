import { brotliCompressSync, deflateSync, gzipSync, zstdCompressSync } from 'node:zlib';
import type { FastifyReply, FastifyRequest } from 'fastify';

type CompressionEncoding = 'zstd' | 'br' | 'gzip' | 'deflate' | 'identity';

function selectEncoding(acceptEncodingHeader: string | undefined): CompressionEncoding {
  if (!acceptEncodingHeader || acceptEncodingHeader.trim() === '') {
    return 'identity';
  }
  const ranked = acceptEncodingHeader
    .split(',')
    .map((entry) => {
      const [nameRaw, ...params] = entry.trim().split(';');
      const name = (nameRaw ?? '').trim().toLowerCase();
      let q = 1;
      for (const param of params) {
        const [keyRaw, valueRaw] = param.split('=');
        if (keyRaw?.trim().toLowerCase() === 'q') {
          const parsed = Number.parseFloat((valueRaw ?? '').trim());
          if (Number.isFinite(parsed)) q = parsed;
        }
      }
      return { name, q };
    })
    .filter((entry) => entry.q > 0);
  const has = (name: string) => ranked.some((entry) => entry.name === name || entry.name === '*');
  if (has('zstd')) return 'zstd';
  if (has('br')) return 'br';
  if (has('gzip')) return 'gzip';
  if (has('deflate')) return 'deflate';
  return 'identity';
}

export function sendCompressedJson(
  request: FastifyRequest,
  reply: FastifyReply,
  statusCode: number,
  payload: unknown,
): void {
  const responseBody = JSON.stringify(payload);
  const acceptEncoding =
    typeof request.headers['accept-encoding'] === 'string'
      ? request.headers['accept-encoding']
      : undefined;
  const encoding = selectEncoding(acceptEncoding);
  const responseBytes = Buffer.from(responseBody, 'utf8');
  const compressedBytes =
    encoding === 'zstd'
      ? zstdCompressSync(responseBytes)
      : encoding === 'br'
        ? brotliCompressSync(responseBytes)
        : encoding === 'gzip'
          ? gzipSync(responseBytes)
          : encoding === 'deflate'
            ? deflateSync(responseBytes)
            : responseBytes;

  // Prevent @fastify/compress from transforming an already encoded payload.
  reply.header('x-no-compression', '1');
  reply.header('Vary', 'accept-encoding');
  reply.header('Content-Type', 'application/json; charset=utf-8');
  if (encoding !== 'identity') {
    reply.header('Content-Encoding', encoding);
  }
  reply.code(statusCode).send(compressedBytes);
}
