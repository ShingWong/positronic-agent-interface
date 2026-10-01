# User guide

For people using positronic to watch a mailbox, an inbox, or any stream of
events — and for anyone who needs it to behave differently from the stock
setup.

This guide assumes no background. If a technical term is unavoidable, it is
defined where it appears. Every number here was measured on a real 38,245-message
mailbox; nothing is estimated. Where a figure is a guess, it says so.

---

## 1. What the system does

You give it events — for mail, one event per message. For each one it makes two
decisions.

**Is this worth remembering?** Most of what arrives is not. It scores each event
from 0 (completely routine) to 1 (completely new) and stores it only if the
score clears a threshold. On a real mailbox the stock setting stores roughly
**36% of messages** (measured on 8,000 recent messages; the figure is 27% on the
full 38,245-message mailbox, because an older mailbox has more repetition to
learn from). The rest are read past and forgotten, which is the point: a system that stored everything would be a filing cabinet, not a memory.

**Is this message dangerous?** Separately, a threat scorer labels each message
`clean`, `spam`, `scam`, or `phishing`. An optional per-brain configuration adds
categories such as `policy` and `illegal`. This label drives the alert in the
Thunderbird plugin and the tag written onto the mail itself.

These two are separate. A message can be unremarkable and safe, or routine and
dangerous, or brand new and harmless. The gate asks "should I keep this?"; the
threat scorer asks "should a human look at this?".

Everything else — how quickly things fade, how long they last, which words
trigger which alert — is a setting. This guide is mostly about those settings.

---

## 2. Two situations, two setups

The same code serves two jobs that are genuinely different.

**Bulk archive ingestion.** Tens of thousands of historical messages loaded
once, to be searchable later. You want almost everything kept, and you want the
load to finish.

**One person's live mailbox.** A few hundred messages a day, where the point is
to notice the dangerous ones and forget the rest.

The stock settings sit between these, which suits neither perfectly. That is why
the settings exist.

A rough guide:

| | Archive ingestion | Live mailbox |
|---|---|---|
| How much arrives | thousands, once | tens per day, forever |
| What you want kept | nearly all | the unusual |
| `threshold` | lower, e.g. `0.35` | stock `0.55`. Never above 0.6. |
| `w_novelty` | stock `0.5` | lower, e.g. `0.35`, to store less |
| `semantic_novelty_window` | larger, e.g. `256` | stock `64` |

The reasoning is in section 5. Change one setting at a time, so you can tell
which one did what.

---

## 3. Setting the knobs

Each brain ("brain" = one named memory store) carries its own settings. Nothing
is global.

```bash
# See what a brain is set to
positronic config --brain mymail

# Change one knob
positronic config --brain mymail --key threshold --set 0.35
positronic config --brain mymail --key w_novelty --set 0.35

# Several at once
positronic config --brain mymail --key engine --set '{"w_novelty":0.35,"semantic_novelty_window":256}'
```

**A misspelled knob is rejected, not ignored.** You will get an error naming the
knobs that exist. This is deliberate: the system previously accepted a setting
like `threshold` and then ignored it, so you believed you had configured
something you had not. That failure is fixed, and misspelling is now caught.

### The memory-gate knobs

The gate computes a score from three parts and stores the event if that score
reaches `threshold`:

```
score = w_novelty × novelty  +  w_arousal × arousal  +  w_gain × importance
```

**`threshold` — the deciding line.** Default `0.55`. An event is stored when
`score` reaches this.
* Lower it to store more. `0.35` suits archive ingestion.
* Raise it to store less. `0.75` suits a mailbox you want to keep quiet.
* Range 0 to 1. Values outside are rejected.

**`w_novelty` — how much newness counts.** Default `0.5`. Scales the influence of
"how unlike anything seen recently is this".
* Lower it and routine-but-unrecognised events are stored more readily.
* Raise it and only genuinely new events are kept.

**`w_arousal` — how much emotional intensity counts.** Default `0.3`. Applies
only if you set an `arousal` value on incoming events; mail ingestion leaves it
at zero, so this knob does nothing for mail today.

**`w_gain` — how much matters who it is from.** Default `0.2`. Uses a learned
weight per sender, so mail from people you correspond with regularly counts for
more.

**`semantic_novelty_window` — how far back to compare.** Default `64`. The
number of recently stored events a new event is compared against.
* Raise it and novelty means "unlike anything in the last N things kept".
* Lower it and novelty means "unlike the last few".
* Measured cost: 16 → 27 µs per event, 64 → 75 µs, 256 → 222 µs. It is the
  main reason to check the cost before raising it.

**`semantic_novelty` — the second opinion, on or off.** Default on. When no
pattern predicted an event, the system compares its wording against recent
memory. Set to `false` to restore the older behaviour where an unexplained
event was always treated as highly new.

**`semantic_novelty_fallback` — what to assume with no text to compare.**
Default `0.9`. Only matters for events with no comparable content.

**`burst_threshold` — the panic line.** Default `0.90`. An event at or above
this is always stored, whatever `threshold` is. Used for escalation.

**`rule_min_confidence` — when to stop believing a pattern.** Default `0.05`. A
learned pattern that has been repeatedly wrong stops counting toward novelty.
It is still kept, and it can recover if it starts working again.

**`rule_antecedent` / `rule_outcome` — what the system predicts.** Default
`subject_norm` → `sender`. These are *field names on your events*, not
instructions. Measured on a real mailbox: these settings let the system predict
the sender from the subject line on **26%** of messages. Setting
`rule_antecedent` to `sender` and `rule_outcome` to a recipient field raised that
to **92%**, but dropped accuracy from 60% to 17% — more predictions, far fewer
correct ones. A high-coverage setting is not automatically a good one.

**`induce_after` / `induce_top_assoc_min` — how much repetition before learning
something.** Defaults `3` and `2`. Raise to be more conservative about what
counts as a pattern.

**`min_semantic_sim` — how similar two texts must be to count as related.**
Default `0.35`. Only used when an embedder is connected.

**`anchor_salience` — how important a memory must be to be treated as
foundational.** Default `0.85`.

**`tau_per_surprise` — how fast the internal clock moves.** Default `1.0`.
Rarely needs changing.

**`entity_extraction`** — default on. Whether to pull out named entities.

---

## 4. The alert categories

The threat scorer is a **score**, not a verdict. Each category collects weight
from the signals that fired; the highest-priority category reaching its
threshold wins. `clean` means nothing reached a threshold.

Stock categories:

| Tag | Means | Fires when |
|---|---|---|
| `phishing` | Credential theft | a link to another domain alongside words like "sign in" or "verify"; or a link to a bare IP address; or a look-alike internationalised domain |
| `scam` | Financial fraud | a fraud phrase **and** a sender you have never received mail from |
| `spam` | Bulk junk | a known junk phrase |
| `clean` | Nothing found | — |

Note `scam` needs **both** conditions. A fraud phrase from a correspondent you
know is not tagged — that combination is usually a forwarded warning, not an
attack.

### What each message tells you

```json
{
  "tag": "phishing",
  "reasons": ["credential-link:phish.example", "fake-context:adobe"],
  "scores": {
    "phishing": {"score": 1.0, "threshold": 1.0, "fired": true},
    "scam":     {"score": 0.0, "threshold": 2.0, "fired": false}
  }
}
```

`reasons` is the evidence. `scores` shows how close each category came, so an
alert can explain itself or show a near miss instead of only a label.

### Adding your own categories

No code change and no release. Add a category to the brain's config:

```bash
positronic config --brain mymail --key threat --set '{
  "categories": [{
    "tag": "policy",
    "priority": 95,
    "threshold": 1.0,
    "signals": [{"id":"policy-lexicon","kind":"lexicon","weight":1.0,
                 "terms":["material nonpublic","trade secret"]}]
  }]
}'
```

Four fields:

- **`tag`** — the label that appears in the alert and on the mail.
- **`priority`** — higher wins when several categories qualify. Stock values:
  phishing 100, scam 90, spam 80. A new category at 95 sits between phishing and
  scam.
- **`threshold`** — how much weight this category needs. A single signal of
  weight 1.0 needs threshold `1.0`. Two signals at 1.0 need `2.0` to require
  both.
- **`signals`** — what to look for, and how much each is worth. `weight: 0`
  records the finding in `reasons` without affecting the tag.

Available signal kinds: `lexicon` (word list), `new_sender`, `foreign_link`,
`credential_link`, `ip_link`, `punycode_link`, `brand_context`, and
`custom_text` (your own regular expression).

**Naming a category replaces it. Categories you do not name keep their stock
behaviour.** So adding `policy` leaves phishing, scam and spam exactly as they
were — confirmed by test.

Two ready-made profiles in `docs/examples/`:
- `threat-consumer.json` — the stock behaviour, written out.
- `threat-enterprise.json` — adds `policy` and `illegal` categories.

To turn threat scoring off for a brain entirely: `--key threat --set false`.

---

## 5. What to expect after a change

You need a number to compare against, or you cannot tell whether a change
helped. All figures below were measured on real mail, on a window of the most
recent 8,000 messages.

### Lowering `threshold`

| `threshold` | Messages stored |
|---|---|
| 0.25 | 61.8% |
| 0.35 | 58.9% |
| 0.45 | 50.8% |
| **0.55 (stock)** | **36.3%** |
| 0.65 | 0.0% — see the warning below |

### ⚠ Never set `threshold` above 0.6

Above 0.6 the system stops storing **anything at all**, silently. It is not a
gradual reduction.

This is arithmetic, not a tuning choice. The gate builds a score from three
weighted parts, and mail ingestion sends `arousal` as zero, so the intensity
term contributes nothing:

```
best achievable score = w_novelty × 1.0  +  w_arousal × 0  +  w_gain × 0.5
                      = 0.5              +  0               +  0.1
                      = 0.6
```

A threshold above 0.6 can never be reached, so every event is rejected. If you
want to store less, lower `w_novelty` instead of raising `threshold` — that
moves the achievable range with it.

### What `w_novelty` does

Lower it and more routine events are stored, because a high score no longer
requires real newness. For archive ingestion this is usually what you want —
you already know the mail is historical, so "is this new?" is the wrong
question to be asking.

### Changing `semantic_novelty_window`

Measured at the stock threshold:

| Window | Messages stored | Cost per event | Novelty means |
|---|---|---|---|
| 16 | 47.4% | 27 µs | unlike the last few |
| **64 (stock)** | **36.3%** | 75 µs | unlike the last 64 things kept |
| 256 | 27.4% | 222 µs | unlike the last 256 |

A larger window makes "new" stricter, because there is more to be unlike. If you
raise it and almost nothing is stored, that is why.

Turning the second opinion off entirely at the stock threshold stores **82.7%**
of messages. That is the older behaviour, in which anything unexplained was
treated as highly new.

### The cost of all this

The gate is a small part of processing a message. Handling one message end to end
takes about 117 milliseconds on the test machine, of which the gate was measured
at 43 microseconds. With the second opinion on at the stock window it is roughly
118 microseconds — under one tenth of one percent.

---

## 6. Tuning cookbook

**"My alerts stopped firing."**
Check `threat` is not set to `false` for that brain. If a category was
overridden, naming it replaced the stock version entirely — check the config.
If you added `scam` terms, note that category requires both a phrase and an
unknown sender; a known sender will not trip it.

**"Everything is being tagged."**
Stock `scam` needs an unknown sender. If your sender list is incomplete, real
contacts look new. Then raise a category's `threshold` above the sum of its
signal weights to disable it, or remove its signals.

**"Nothing is ever remembered."**
Raise `semantic_novelty_window` and the scores drop, so fewer events clear the
line. Either lower it or lower `threshold`. Confirm which: run with
`semantic_novelty: false` — if messages suddenly appear, the second opinion is
the cause.

**"The same message is stored over and over."**
The gate is scoring it as new each time. If it repeats verbatim it should score
near zero. If it does not, the words differ between copies. `dedup` exists for
exact repeats by message id.

**"I set `threshold` and nothing changed."**
Before version `d5308e4` this setting was written to your config and then
ignored, because the engine was never given its configuration. It is now
honoured. If you set it before that version, re-check the value you expect.

**"Which knobs exist?"**
`positronic config --brain mymail` prints the brain's current settings.

---

## 7. Reference

| Knob | Default | Direction |
|---|---|---|
| `threshold` | 0.55 | lower stores more |
| `w_novelty` | 0.5 | lower stores more routine events |
| `w_arousal` | 0.3 | higher stores more emotionally intense events |
| `w_gain` | 0.2 | higher trusts known senders more |
| `semantic_novelty_window` | 64 | larger = stricter novelty, slower |
| `semantic_novelty` | true | false restores old behaviour |
| `semantic_novelty_fallback` | 0.9 | only for textless events |
| `burst_threshold` | 0.90 | always stored at or above |
| `rule_min_confidence` | 0.05 | higher distrusts learned patterns sooner |
| `rule_antecedent` | `subject_norm` | field to predict from |
| `rule_outcome` | `sender` | field to predict |
| `induce_after` | 3 | higher learns patterns later |
| `induce_top_assoc_min` | 2 | higher needs firmer agreement |
| `min_semantic_sim` | 0.35 | only with an embedder connected |
| `anchor_salience` | 0.85 | higher promotes fewer memories |
| `tau_per_surprise` | 1.0 | higher speeds the internal clock |
| `entity_extraction` | true | false disables entity extraction |

---

## 8. Known limitations

Stated plainly, because you will otherwise hit them and assume a bug.

- **`threshold` above 0.6 disables storage entirely.** Not gradually — totally,
  and without an error. See section 5. This is the sharpest edge in the whole
  system and it is a defect, not a design choice.
- **How much is stored depends heavily on how much text each event carries.**
  The second opinion compares wording, so short repetitive events are scored as
  near-duplicates and mostly dropped. On real mail averaging a subject line, the
  stock setting stores 36%. On a synthetic feed of four-word messages from a
  fifteen-word vocabulary it stored **0.1%** — every message looked like every
  other. Check your own numbers rather than assuming mine apply to you.
- **Threat scoring is a keyword and link matcher.** It does not understand
  meaning. An unusual attack phrased without any listed term will pass. Treat
  every non-`clean` tag as "worth a human look", never as proof.
- **`illegal` in particular is a prompt, not a finding.** The categories in the
  enterprise example exist to route mail to someone who can judge it.
- **Sender history counts messages, not trust.** A sender with one message and
  a sender with two thousand are both "not new" once seen.
- **The stock lexicon is English and consumer-oriented.** It will miss other
  languages and domain jargon until you add terms.
- **Novelty compares wording, not meaning.** Two messages saying the same thing
  in different words score as unrelated. A text embedder connected to the brain
  improves retrieval; it does not currently change the novelty score.