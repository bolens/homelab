import randomId from './randomId';

describe('randomId', () => {
  it('returns a string of the requested length', () => {
    expect(randomId(8)).toHaveLength(8);
  });

  it('uses base36 characters', () => {
    expect(randomId(12)).toMatch(/^[a-z0-9]+$/i);
  });
});
