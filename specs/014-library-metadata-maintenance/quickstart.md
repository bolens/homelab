# Validation

Run focused tests from `stacks/mylar3/config` using `python3 -m unittest test_library_metadata test_metadata_repair test_tagger_archive test_tagger_adapter test_tagger_nfs test_converted_tagging`.

Run `stacks/mylar3/verify-image.sh IMAGE_REFERENCE` against the candidate image and `make validate` before delivery. The image gate uses isolated fixtures without live mounts.

After verified deployment, enable each option separately in Activity. Confirm an exact untagged fixture enters Converted comic tagging once, a agreeing nested fixture retains provenance with one root ComicInfo, and a conflicting fixture is unchanged and shown for review. Verify idle-only processing and saved settings. Use simulated interruption checks, never real power loss.
