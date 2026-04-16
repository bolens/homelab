declare module 'json2csv' {
  export class Parser<T = Record<string, unknown>> {
    constructor(opts?: { fields?: string[] });
    parse(data: T[]): string;
  }
}
