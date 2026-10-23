#!/usr/bin/env python3
"""Python port of RSpec::Core::Ordering::Random (rspec-core 3.13.6, target/src-excerpts/ordering.rb
lines 25-58): items.sort_by { jenkins_hash_digest(seed.to_s + item.id) }.
Predicts, per order seed, whether the Cart polluter [1:2] runs before the victim [1:1].
UNPROVEN until the Ruby run in the Cursor task reproduces it (acceptance step A3)."""
import json, sys
M = 4_294_967_295
def jenkins(s):
    h = 0
    for b in s.encode():
        h += b; h &= M
        h += (h << 10) & M; h &= M
        h ^= h >> 6
    h += (h << 3) & M; h &= M
    h ^= h >> 11
    h += (h << 15) & M; h &= M
    return h
V, P = "./spec/models/cart_spec.rb[1:1]", "./spec/models/cart_spec.rb[1:2]"
def victim_fails(seed):
    hv, hp = jenkins(str(seed) + V), jenkins(str(seed) + P)
    assert hv != hp, seed
    return hp < hv            # sort_by ascending: polluter first -> victim sees discount 10
if __name__ == "__main__":
    seeds = range(0, 100)
    out = {"victim": V, "polluter": P, "seeds": "0..99",
           "victim_fails": [s for s in seeds if victim_fails(s)],
           "victim_passes": [s for s in seeds if not victim_fails(s)]}
    json.dump(out, sys.stdout, indent=1); print()
