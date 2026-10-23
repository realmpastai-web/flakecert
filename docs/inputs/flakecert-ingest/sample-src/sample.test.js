function rng(seed){ let x = seed >>> 0 || 1; return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return ((x >>> 0) % 1000) / 1000; }; }
test('pass', () => { expect(1 + 1).toBe(2); });
test('fail deterministic', () => { expect({a: 1}).toEqual({a: 2}); });
test('flaky seeded', () => { const r = rng(parseInt(process.env.SEED || '0', 10))(); expect(r).toBeGreaterThanOrEqual(0.5); });
test.skip('skip', () => {});
