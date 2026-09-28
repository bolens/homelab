# First-increment evidence

Scope: process and metadata foundation only, against baseline `060b782`.

- 12 real-process tests: success, exit failure, missing executable/cwd, stdin EOF,
  literal arguments, timeout, inherited pipes, output limits and secret-free repr.
- 15 XML tests: explicit volume 1/start year, paired arcs, partial/mismatched arc
  rejection, preservation, explicit overwrite policy, malformed/oversized/DTD XML.
- Independent runtime/transport-plan review: no blocking finding; clarified direct
  child reaping versus process-group termination before future real-CLI activation.
- Independent metadata/build-contract review: fixed fabricated arc pairing with
  three regressions that failed before the fix. Re-review passed all 15 tests.
- Candidate pinned-image build passed the complete 232-test Mylar gate without skips.

These results establish R1/M1/M2 helper behavior only. C1-C4, N1-N3, P1 modern-runtime,
L1 and D1-D4 remain pending. The build does not install or activate modern ComicTagger
or curl. No live configuration, library files or services were changed.

`make ci-local` passed. Publication scanning found no secrets or privacy indicators
in 107 Mylar files and 10 feature documents, with no skips. Gitleaks scanned 372
commits with no findings. PR publication is the remaining delivery step for this
increment; subsequent capability tasks remain unchecked.
