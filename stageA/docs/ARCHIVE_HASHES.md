# Release archive hashes (SHA-256)

Computed on the archives as delivered. A deployed copy is checked against this list before unzipping
(`sha256sum`), and the value is
written to `~/stageA/ARCHIVE_SHA256.txt`, which every run manifest records. An archive cannot contain its own
hash; the hash of the current release is in the next release's list and in the message that delivered it.

| archive | SHA-256 |
|---|---|
| stageA_v0.2.4.zip | 9bf26fe74d8105b089d7a74059e9d71fe1e0d653616d68b11bf094acdf6392f9 (first release with the frozen set) |
| stageA_v0.3.zip | 1dbafc9e2b5887d3361b173369334cf4f33b5aa1c42d4c81fff07610d521c98a |
| stageA_v0.3.1.zip | 889b42255febe1845858bc349b66d5d64736bad1c85b64caf9f004b66aa5d47c |
| stageA_v0.3.2.zip | e029a25c0aa313ddf3029414126e04b5b6e925f4decf5715871e2000f812a46c |
| stageA_v0.3.3.zip | 061a0cb9ff63bc1fe773723e970bdb4ba5c19f394b884a94f34cb5b98cbe9500 |
| stageA_v0.3.4.zip | 6f8e6881ea2fc8b78591c51f6ee1bf91807492d64755c55b4e23d3d1ca39ea40 |
| stageA_v0.3.5.zip | 4249adbefea7104b78531f5c7b3b987aa10ee7fa05d3857461131ea01b741720 |
| stageA_v0.3.6.zip | 1db4b78ea1e012cfb18334f925149a7c4bd3bba0e88bb5f1adf9c2919a320057 |
| stageA_v0.3.7.zip | ef55b944dbafc55107e06370afb415802728e04a3386be07715602e8147f0131 (never deployed) |
| stageA_v0.3.8.zip | dea890bd0b86420089939b1ef3c8d70518d8d37188dc4bbe4050dcbdbff2a0b6 (uploaded and hash-checked on the cluster, never unzipped or run) |
| stageA_v0.3.9.zip | c733afd85969ac29564e5bf448fb361bbcbebee915cf89b9d31de5fda2285e4c (deployed 2026-10-02; replays 115387-115389 were submitted with it) |

`docs/FROZEN_TEST_SET.json` (frozen 2026-10-01) is byte-identical in all of them (checked from each archive on 2026-10-02): its SHA-256 is
bd7890f38fce71c1dea8fe37b64331d81c3fac0de1abf6f050d0d0595ec8ba7f (`scripts/freeze_test_set.py --verify`
also recomputes every test instance and compares it with the file).

The runs in the paper used an earlier v0.3 release (discovery of the earlier development batch), v0.3.9
(above), v0.3.10 and v0.3.10.1; the hashes of the last two archives are
recorded in the run manifests (`archive_sha256`). None of these archives is the anonymized archive released
for review, so none of these hashes matches it.
