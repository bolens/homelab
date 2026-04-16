/**
 * @param length — number of random base36 characters
 */
const randomId = (length: number): string =>
  Math.random()
    .toString(36)
    .slice(2, 2 + length);

export default randomId;
