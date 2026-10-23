# Review summary for issue #47 / PR #60 feedback

Related: #47, #59, #60. Does not close #47.

Corrects the synthetic starter's source labels and render consistency, expands
development templates and controlled degradation, and provides a directly usable
TV3 data package with transcripts. Adds independent source QA, public-source audit,
pinned download/import adapters, statistics, reviewed evidence linking, a guarded
freeze inventory and evaluation-table export. Adds CI and six small fixtures;
large generated and public datasets stay out of Git.

Validation: 102 dataset/KIE/document-reader tests, Ruff, 30-base/510-variant QA,
three real reader+KIE routes and actual public train subsets. No final accuracy
claim; no final dataset was silently promoted or frozen.

Review requested from lead/TV3/TV4 after publication. No owner review is claimed.
Frontend/backend contracts are unchanged; TV3 receives existing benchmark JSON;
TV4 consumes source gold only after reviewed evidence linkage. DevOps receives a
new additive QA workflow. An additive public development evaluator applies
supported-field masks to reviewed actual evidence/predictions; it does not
change TV4's strict full-invoice evaluator or claim canonical invoice accuracy.

Outstanding: official SROIE access/archive, independent author/reviewer and mock
final set, reviewed source-to-block links, final configuration/protocol freeze,
actual final predictions/tables, and second-machine reproduction.
