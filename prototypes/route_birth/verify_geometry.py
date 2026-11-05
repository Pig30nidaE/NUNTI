#!/usr/bin/env python3
"""Check route influence independently of journey nonce, without model work.

Imports only the pure generator entry points and treats their results as external
artifacts. No model library, network, APK or persistent worker state is used.
Numeric differences are not a claim of perceptually unique or cute characters.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import random
import uuid

from generator import geometry, make_plan, normalize
from verify_http import canonical, request_input, require, sha, validate_visual


def rmse(first, second):
    return math.sqrt(sum((a - b) ** 2 for p, q in zip(first, second) for a, b in zip(p, q)) / (len(first) * 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Evidence output must be new')
    fixed_nonce = 'ae5ce218-63a8-4330-a9d6-ab619ad79921'
    routes = {
        'horizontal': [[.1, .5], [.9, .5]],
        'vertical': [[.5, .1], [.5, .9]],
        'rising_diagonal': [[.1, .9], [.9, .1]],
        'broad_zigzag': [[.1, .1], [.9, .3], [.1, .55], [.9, .9]],
        's_bend': [[.2, .9], [.8, .7], [.8, .55], [.2, .4], [.2, .15], [.8, .1]],
        'loop': [[.5, .1], [.9, .3], [.9, .7], [.5, .9], [.1, .7], [.1, .3], [.5, .1]],
        'tight_hairpin': [[.2, .9], [.2, .1], [.3, .1], [.3, .9], [.4, .9], [.4, .1]],
        'almost_point': [[.5, .5], [.500002, .5]],
    }
    randomizer = random.Random(926432)
    for i in range(128):
        count = randomizer.randint(2, 80)
        routes['random-' + str(i)] = [[randomizer.random(), randomizer.random()] for _ in range(count)]
    proofs, visuals = [], {}
    for label, points in routes.items():
        request = request_input(points=points)
        request['requestId'] = fixed_nonce
        parsed = normalize(request)
        visual, signals = geometry(parsed['route']['points'], fixed_nonce, parsed['destination']['traits'], parsed['purpose'])
        repeated, repeated_signals = geometry(parsed['route']['points'], fixed_nonce, parsed['destination']['traits'], parsed['purpose'])
        require(canonical(visual) == canonical(repeated) and signals == repeated_signals, 'Pure geometry is not repeatable')
        visual_proof = validate_visual(visual)
        plan = make_plan(request, '0' * 64, {'purpose': 'independent-no-model-test'})
        require(plan['artifact']['visual'] == visual, 'Plan geometry differs from pure input route geometry')
        proofs.append({'case': label, 'inputPointCount': len(points), 'signals': signals,
                       'directionSha256': sha(plan['artifact']['voice']['direction'].encode()), **visual_proof})
        visuals[label] = visual
    require(len({v['outlineSha256'] for v in proofs}) == len(proofs), 'Different routes at identical nonce reused exact outline')
    comparisons = [{'first': a, 'second': b, 'outlineRmse': rmse(visuals[a]['outline'], visuals[b]['outline']),
                    'samePalette': visuals[a]['palette'] == visuals[b]['palette']}
                   for a, b in itertools.combinations(list(routes)[:8], 2)]
    require(all(p['outlineRmse'] > 0 for p in comparisons), 'Fixed-nonce route did not influence outline')
    # Same route with independent UUIDs: identity remains tied to each journey.
    same_route_plans = [make_plan({**request_input(points=routes['s_bend']), 'requestId': str(uuid.UUID(int=i + 1))},
                                 '0' * 64, {'purpose': 'independent-no-model-test'}) for i in range(40)]
    require(len({p['artifact']['characterId'] for p in same_route_plans}) == 40, 'Different journeys reused character identity')
    require(len({sha(canonical(p['artifact']['visual']['outline'])) for p in same_route_plans}) == 40,
            'Different sampled journey nonces reused exact outlines')
    report = {'status': 'PASS_ROUTE_INFLUENCE_WITH_FIXED_NONCE_AND_CONTINUOUS_GEOMETRY',
              'at': datetime.now(timezone.utc).isoformat(), 'generatorSha256': sha(Path(__file__).with_name('generator.py').read_bytes()),
              'fixedNonce': fixed_nonce, 'fixedNonceRouteCount': len(proofs), 'sameRouteNewJourneyCount': 40,
              'modelLoaded': False, 'proofs': proofs, 'curatedPairComparisons': comparisons,
              'minimumCuratedOutlineRmse': min(p['outlineRmse'] for p in comparisons),
              'notVerified': ['Mathematical uniqueness across all possible inputs', 'Perceptual uniqueness, cuteness, collectibility',
                              'Native rendering', 'TTS synthesis, playback or human quality']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'fixedNonceRouteCount', 'sameRouteNewJourneyCount', 'minimumCuratedOutlineRmse')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
