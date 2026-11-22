"""Tier 2 Boundary & Corner Cases Test Suite for ParkMyCar ANPR & Live Occupancy Tracking.

Contains 50 test cases across 10 boundary modules:
- test_b1_ambiguity.py: T2-B1-01 .. T2-B1-05 (Character ambiguity extremes 0/O, 1/I, 8/B, 5/S, 2/Z)
- test_b2_syntax.py: T2-B2-01 .. T2-B2-05 (Malformed syntax, lowercase, invalid state codes, symbols)
- test_b3_aspect_ratios.py: T2-B3-01 .. T2-B3-05 (Extreme aspect ratios 10:1, 1:2, tiny 20x10, 4K)
- test_b4_degraded_crops.py: T2-B4-01 .. T2-B4-05 (Heavy blur, noise, partial occlusion, overexposure)
- test_b5_out_of_order.py: T2-B5-01 .. T2-B5-05 (Out-of-order exit before entry, duplicate exits, inverted timestamps)
- test_b6_burst_concurrency.py: T2-B6-01 .. T2-B6-05 (Rapid burst events, simultaneous entries, race condition handling)
- test_b7_capacity_limits.py: T2-B7-01 .. T2-B7-05 (Zero capacity, full capacity 900 saturation, overflow handling)
- test_b8_durations.py: T2-B8-01 .. T2-B8-05 (1 second stay, 30 day overstay, negative timestamp prevention)
- test_b9_camera_flapping.py: T2-B9-01 .. T2-B9-05 (Rapid disconnect/reconnect flapping, heartbeat timeout)
- test_b10_security_auth.py: T2-B10-01 .. T2-B10-05 (Missing X-ANPR-Secret, invalid secret, wrong content-type, SQL injection attempt in plateNumber)
"""
