# Diagnostic recipes: mail logs

Proven queries for a postfix/amavis log brain. Each one ran against the
30k-line mx1 slice (19,999 episodes); counts below are from that corpus, so
yours will differ. SQL is read-only by design -- writes are refused.

Setup (two commands, no scripts):

    positronic init --brain mx1 --from-db /path/memory.db
    # or build from the file:
    positronic ingest-log --schema postfix-maillog/schema.yaml --file maillog \
      --since <iso> --until <iso> --brain mx1 --skip-validate

Start every session with `query --describe --brain mx1`. It prints the
tables, the `features_json` key conventions for THIS corpus, and counts.
Field names differ per schema (`message` vs `body_text`); the sample shows
what is actually here.

## 1. Top offender sessions for one class

    SELECT json_extract(features_json,'$.identity_canonical') s, COUNT(*) n
    FROM episode WHERE level='event'
      AND json_extract(features_json,'$.event_class')='sasl_login_failed'
    GROUP BY s ORDER BY n DESC LIMIT 10

Result here: `postfix/submission/smtpd:28801` (30), `:28541` (28),
`:28532` (28). Follow-up per session:

    positronic query --object session:28801 --brain mx1

A bare pid resolves; the dossier lists the full life oldest-first.

## 2. Verdict distribution

    SELECT COUNT(*) c FROM episode WHERE level='event'
      AND features_json LIKE '%Passed SPAM%'

Result here: 16 in the slice (68 in the full 300k-line file). CLEAN, BLOCKED
variants work the same way. This counts verdict *lines*; one mail yields one
verdict line, so the count is mails.

## 3. Snowshoe detector: unknown EHLO plus throwaway domains

    SELECT COUNT(*) c FROM episode WHERE level='event'
      AND features_json LIKE '%client=unknown[104.168.13%'

Result here: 12 lines from one /24, each arriving as `client=unknown[...]`
-- no reverse DNS, no EHLO forgery attempted. Cross-check the sender
domains in the same window: disposable `.shop` / `.pro` families at 3 mails
each is the same operation spreading load. Legitimate senders in this file
identify themselves (`vps-....vps.ovh.ca`); the unknown-EHLO cluster does
not.

## 4. Delivery finder, then dossier

Find the queue id by sender and recipient:

    SELECT id FROM episode WHERE level='event'
      AND features_json LIKE '%sadie.cox@capitalacquisitionasset.com%'
      AND features_json LIKE '%wong@accesscom.net%'
    ORDER BY wall DESC LIMIT 5

Then open each queue id:

    positronic query --object message:queue:303B1142F0D37 --brain mx1

The dossier names every session that touched the message (`carried_by`)
across the filter re-injection (pre-filter and post-filter queue ids link
through the same line). Proven case: 11 episodes, 6 layers, intake to
dovecot delivery.

## 5. Deferred mail with delay breakdown

    SELECT wall,
      substr(COALESCE(json_extract(features_json,'$.message'),
                      json_extract(features_json,'$.body_text'),''),1,120) m
    FROM episode WHERE level='event'
      AND features_json LIKE '%status=deferred%'
    ORDER BY wall DESC LIMIT 20

Result here: 486 delay lines; the morning example is
`to=<photos@onedrive.com>, delay=65752, dsn=4.4.1, status=deferred`.
Read `delays=a/b/c/d` as before-queue-manager / queue / connection-setup /
transmission. `delay=` is seconds; 65752 is 18 hours of retrying.

## Caveats, stated plainly

- Query by TEXT (`status=`, `client=`), not by class. Delivery lines in
  this corpus carry `event_class: null` (the unclassified remainder); a
  `WHERE event_class='...'` clause silently misses them.
- Counts are episode-level within the ingested window. A different slice
  gives different numbers; the recipes do not.
- `--object` needs the queue id first: recipe 4 is the finder, the dossier
  is the follow-up. Neither works alone.
- Subjects, bodies, and unicode tricks are NOT in a maillog (postfix never
  logs headers; the file is pure ASCII). For content questions, ingest the
  amavis quarantine, not the log.
