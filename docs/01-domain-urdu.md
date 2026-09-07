# 01 — Urdu Domain Knowledge

> Read this before implementing `app/normalizer/` or `app/extractor/`.
>
> **Everything here is data, not logic.** Load these tables from Python dicts or
> JSON. Never hardcode an Urdu string inside an `if` branch — the tables will be
> corrected by a native speaker and the logic must not need touching.

---

## 1. Why this file exists

The normalizer and extractor encode facts about how Pakistani shopkeepers
actually speak. These facts cannot be inferred from general knowledge and
getting them wrong produces **silent monetary errors** — a wrong number that
parses cleanly and passes every automated check.

If a case is not covered here, **stop and ask**. Do not guess an Urdu word,
spelling, or numeric value.

---

## 2. Orthographic folding

Recognition output is inconsistent about which Unicode variant it emits for the
same letter. Fold before any comparison.

```python
# Urdu-Indic (U+06F0-06F9) and Arabic-Indic (U+0660-0669) digits -> ASCII
DIGIT_MAP = str.maketrans(
    "\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9"
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "01234567890123456789",
)

CHAR_FOLD = {
    "\u0623": "\u0627",   # alef with hamza above -> alef
    "\u0622": "\u0627",   # alef with madda      -> alef
    "\u0625": "\u0627",   # alef with hamza below -> alef
    "\u064A": "\u06CC",   # arabic yeh  -> farsi yeh
    "\u0649": "\u06CC",   # alef maksura -> farsi yeh
    "\u0629": "\u06C1",   # teh marbuta -> heh goal
    "\u0647": "\u06C1",   # arabic heh  -> heh goal
    "\u06BE": "\u06C1",   # heh doachashmee -> heh goal
    "\u0643": "\u06A9",   # arabic kaf -> keheh
}

DIACRITICS = r"[\u064B-\u065F\u0670\u06D6-\u06ED]"
ZERO_WIDTH = r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069]"
```

`urdu_fold(s)` order: strip zero-width → strip diacritics → translate digits →
apply `CHAR_FOLD` → collapse whitespace → strip.

Apply to: every transcript, every SKU `display_name` and alias, every customer
name, both sides of every comparison.

---

## 3. Cardinal numbers 0–99

> ⚠ **DRAFT — REQUIRES NATIVE-SPEAKER VERIFICATION BEFORE THE DEMO.**
> Store as data (`server/data/urdu_numerals.json`) so corrections need no code
> change. Add every Roman-Urdu spelling variant you observe in real transcripts
> as an alias. Recognition often emits digits for larger numbers, so the high
> end of this table matters less in practice than 1–30.

Written **value-first with a Roman gloss** so each line ends in Latin text; this
keeps bidirectional rendering readable in editors and terminals.

```python
URDU_CARDINALS = [
    (0,  "صفر"),        # sifar
    (1,  "ایک"),        # ek
    (2,  "دو"),         # do
    (3,  "تین"),        # teen
    (4,  "چار"),        # chaar
    (5,  "پانچ"),       # paanch
    (6,  "چھ"),         # chhe        (also "چھے")
    (7,  "سات"),        # saat
    (8,  "آٹھ"),        # aath
    (9,  "نو"),         # nau
    (10, "دس"),         # das
    (11, "گیارہ"),      # gyarah
    (12, "بارہ"),       # barah
    (13, "تیرہ"),       # terah
    (14, "چودہ"),       # chaudah
    (15, "پندرہ"),      # pandrah
    (16, "سولہ"),       # solah
    (17, "سترہ"),       # satrah
    (18, "اٹھارہ"),     # atharah
    (19, "انیس"),       # unnees
    (20, "بیس"),        # bees
    (21, "اکیس"),       # ikkees
    (22, "بائیس"),      # baees
    (23, "تئیس"),       # taees
    (24, "چوبیس"),      # chaubees
    (25, "پچیس"),       # pachees
    (26, "چھببیس"),     # chhabbees
    (27, "ستائیس"),     # sattaees
    (28, "اٹھائیس"),    # atthaees
    (29, "انتیس"),      # untees
    (30, "تیس"),        # tees
    (35, "پینتیس"),     # paintees
    (40, "چالیس"),      # chaalees
    (45, "پینتالیس"),   # paintaalees
    (50, "پچاس"),       # pachaas
    (55, "پچپن"),       # pachpan
    (60, "ساٹھ"),       # saath
    (65, "پینسٹھ"),     # painsath
    (70, "ستر"),        # sattar
    (75, "پچہتر"),      # pachhattar
    (80, "اسی"),        # assi
    (85, "پچاسی"),      # pachaasi
    (90, "نوے"),        # nawway      (also "نبے" nabbe)
    (95, "پچانوے"),     # pachaanway
    (99, "نانوے"),      # ninaanway
    # GAPS ABOVE ARE INTENTIONAL. A native speaker fills 31-34, 36-39, 41-44,
    # 46-49, 51-54, 56-59, 61-64, 66-69, 71-74, 76-79, 81-84, 86-89, 91-94,
    # 96-98 on Day 1. Every Urdu cardinal is irregular -- there is NO
    # compositional rule you can implement to generate them.
]

URDU_MULTIPLIERS = [
    (100,     "سو"),      # sau
    (1000,    "ہزار"),    # hazaar
    (100_000, "لاکھ"),    # lakh
]
```

### Compound number algorithm

`100` multiplies the current group **in place**. `1000` and above **flush** the
group into the running total. This asymmetry is the whole algorithm.

```
saat sau bees        ->  saat=7  ->  sau: 7*100=700  ->  bees: 700+20=720
do hazaar teen sau   ->  do=2    ->  hazaar: flush 2000, reset
                         teen=3  ->  sau: 3*100=300  ->  total 2300
```

```python
def parse_number_words(tokens: list[str]) -> int | None:
    total, current, seen = 0, 0, False
    for t in tokens:
        if t in CARDINALS:
            current += CARDINALS[t]; seen = True
        elif t in MULTIPLIERS:
            m = MULTIPLIERS[t]
            if m == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * m
                current = 0
            seen = True
        else:
            break                      # stop at the first non-number token
    return (total + current) if seen else None
```

---

## 4. Fractional quantifiers — the highest-risk table in the project

Two grammatically distinct classes. Confusing them is a silent monetary error.

### Class A — standalone values (a complete quantity on their own)

| Urdu | Roman | Value | Note |
|---|---|---|---|
| آدھا | aadha | 0.5 | |
| پاؤ | paw | 0.25 | Conventionally 250 g when the unit is kilo |
| ڈیڑھ | derh | 1.5 | Idiomatic. `sawa ek` is NOT used for 1.25→1.5 |
| ڈھائی | dhai | 2.5 | Idiomatic. `saarhe do` is NOT used |

### Class B — prefix modifiers (apply to the number that FOLLOWS)

| Urdu | Roman | Operation | Example |
|---|---|---|---|
| سوا | sawa | `n + 0.25` | `sawa teen` = 3.25 |
| ساڑھے | saarhe | `n + 0.5` | `saarhe teen` = 3.5 |
| پونے | paun | **`n − 0.25`** | `paun chaar` = **3.75** |

```python
STANDALONE = {word: value for value, word in [
    (0.5,  "آدھا"),      # aadha
    (0.25, "پاؤ"),       # paw
    (1.5,  "ڈیڑھ"),      # derh
    (2.5,  "ڈھائی"),     # dhai
]}

MODIFIER = {word: delta for delta, word in [
    (+0.25, "سوا"),      # sawa
    (+0.5,  "ساڑھے"),    # saarhe
    (-0.25, "پونے"),     # paun   <-- SUBTRACTS. AGENTS.md rule 3.
]}
```

**Dangling modifier.** A Class B word with no following number is genuinely
ambiguous. Return `None`. Do not default to anything.

---

## 5. Units

```python
UNITS_CANON = {word: spec for spec, word in [
    (("kg", 1.0),      "کلو"),        # kilo
    (("kg", 1.0),      "کلوگرام"),    # kilogram
    (("g",  1.0),      "گرام"),       # gram
    (("kg", 0.25),     "پاؤ"),        # paw -- UNIT sense, see below
    (("kg", 0.933),    "سیر"),        # seer      [approximate, verify locally]
    (("g",  58.3),     "چھٹانک"),     # chhataank [approximate, verify locally]
    (("dozen", 12.0),  "درجن"),       # darjan
    (("l",  1.0),      "لیٹر"),       # litre
    (("bottle", 1.0),  "بوتل"),       # bottle
    (("packet", 1.0),  "پیکٹ"),       # packet
    (("box", 1.0),     "ڈبہ"),        # dabba
]}
```

### `paw` is ambiguous — disambiguate by the NEXT token

- Next token is a **unit** → `paw` is a quantifier: `0.25 × that unit`.
  `paw kilo` = 0.25 kg.
- Next token is an **item** → `paw` is the unit itself, meaning 250 g.
  `paw cheeni` = 0.25 kg of sugar.

---

## 6. Function words

```python
HONORIFICS = ["بھائی", "صاحب", "جی", "باجی", "خالہ", "چاچا", "انکل", "آپا"]
#              bhai     sahib    ji    baji     khala   chacha  uncle   aapa
# Dropped from the token stream, BUT their presence RAISES confidence that the
# preceding token is a person's name. Use them as a signal, not just a filter.

GENITIVE_MARKERS = ["کا", "کی", "کے"]      # ka, ki, ke
# Postpositions meaning "of / 's". The span BEFORE one of these is a possessor,
# i.e. the customer. Strongest single customer-identification signal available.

FILLERS = ["اچھا", "ٹھیک", "ہاں", "وہ", "یار", "دیکھو", "اور", "بس", "پھر"]
#           achha   theek   haan   wo    yaar   dekho    aur   bas   phir
# Dropped. No signal value.

NEGATION = ["نہیں", "غلط", "رکو", "ایک منٹ"]
#            nahin   ghalat  ruko   ek minute
# Marks self-correction. Values BEFORE the marker in the same line scope are
# discarded (keep them in `payload` for audit).

UDHAAR_MARKERS = ["ادھار", "خاتہ", "لکھ لو", "لکھ دو", "khata", "udhaar"]
CASH_MARKERS   = ["نقد", "کیش", "ادا", "cash"]
CURRENCY       = ["روپے", "روپیہ", "rupay", "rupees", "PKR", "Rs"]
QUERY_MARKERS  = ["بیلنس", "حساب", "کتنا باقی", "کتنے پیسے", "کتنا ادھار",
                  "آج کا", "balance"]
```

**Payment default:** if neither an udhaar nor a cash marker is present *and* a
customer was identified → default `udhaar` (this app exists to track credit; a
mis-filed cash sale is a smaller error than a lost credit entry). If **no
customer** was identified → default `cash` (a credit entry structurally requires
a person).

---

## 7. Homophones and known ambiguities

### `دو` (do) — "two" vs. the imperative "give"

Highest-frequency ambiguity in this domain.

```python
def classify_do(tokens: list[str], i: int) -> str:
    nxt  = tokens[i + 1] if i + 1 < len(tokens) else None
    prev = tokens[i - 1] if i > 0 else None
    if nxt in UNITS_CANON or nxt in known_item_tokens:
        return "NUMERAL"          # "do kilo" -> 2
    if prev in IMPERATIVE_HEADS or nxt is None:
        return "VERB"             # "de do"   -> drop
    if nxt and nxt.isdigit():
        return "NUMERAL"
    return "AMBIGUOUS"            # -> confirmation, do not guess

IMPERATIVE_HEADS = ["دے", "لے", "کر"]     # de, le, kar
```

### Others

| Pair | Disambiguation |
|---|---|
| `sau` 100 / `so` sleep | Preceded by a cardinal → multiplier |
| `aath` 8 / `haath` hand | Followed by a unit → numeral. Put both in the ASR bias prompt |
| `lakh` 100,000 / `lakhon` many | Implausible in a kiryana sale — validation rule V4 catches it |
| `paw` quantifier / unit | §5 above |
| Customer name == brand name | Adjacent to qty/unit → product. Adjacent to genitive/honorific → customer. Both signals → **ambiguous, ask** |

---

## 8. Required test cases

Write these as tests **before** the implementation. Expected values are
authoritative; do not adjust them to make code pass.

### Normalizer

| Input (Roman) | Expected |
|---|---|
| `dhai kilo` | `qty=2.5, unit=kg` |
| `derh kilo` | `qty=1.5, unit=kg` |
| `paun chaar kilo` | `qty=3.75, unit=kg` |
| `sawa teen` | `qty=3.25` |
| `saarhe saat` | `qty=7.5` |
| `aadha kilo` | `qty=0.5, unit=kg` |
| `paw cheeni` | `qty=0.25, unit=kg` (paw as unit) |
| `paw kilo` | `qty=0.25, unit=kg` (paw as quantifier) |
| `saat sau bees` | `720` |
| `do hazaar teen sau pachaas` | `2350` |
| `sawa` (alone) | `None` → blocking |
| `do kilo` | `qty=2`, `do` classified NUMERAL |
| `de do` | `do` classified VERB, dropped |
| Urdu numerals `۳۰۰` | `300` |
| Mixed `۲` and `2` in one utterance | both → `2` |

### Extractor (order independence)

Same basket, four word orders. **All four must produce identical items.**

| Input | Expected |
|---|---|
| `Ahmed bhai ka, do kilo cheeni, aadha kilo besan` | customer=Ahmed, 2 items, `order_form=canonical` |
| `do kilo cheeni, aadha kilo besan, Ahmed bhai` | customer=Ahmed, 2 items, `order_form=name_last` |
| `do kilo cheeni, Ahmed bhai ka, aadha kilo besan` | customer=Ahmed, 2 items, `order_form=name_medial` |
| `do kilo cheeni, aadha kilo besan` (no draft open) | customer absent, `payment_type=cash`, `order_form=no_name_cash` |
| `aik paw laal mirch` | ONE item (`laal mirch`), not two |
| `do kilo cheeni, Ahmed bhai, Bilal bhai` | two residue spans → **blocking** |
| Unknown word adjacent to a qty | provisional SKU, NOT a customer |
| Unknown word isolated | new-customer candidate |

---

## 9. Demo data requirements

`server/data/catalogue.json` — **40 SKUs**, each with: `sku_id`,
`display_name` (Urdu), `aliases` (Urdu + Roman + English variants),
`default_unit`, `unit_price` (int PKR), `max_plausible_qty`.

Include at least these multi-token names to exercise n-gram matching:
`laal mirch`, `chai patti`, `desi ghee`, `surf excel`, `haldi powder`.

`server/data/customers.json` — ~15 customers, some with deliberately similar
names (two variants of Ahmed, one Ahmad) to exercise the margin check, mixed
balances, varied `last_txn_at` to exercise the recency prior.

`server/data/corpus/manifest.json` — utterance records:

```json
{
  "utterances": [
    {
      "id": "u001",
      "audio": "u001.webm",
      "ground_truth_text": "احمد بھائی کا دو کلو چینی",
      "expected": {
        "customer_id": "CUST_003",
        "order_form": "canonical",
        "items": [{"sku_id": "SKU_012", "qty": 2.0, "unit": "kg"}]
      },
      "tags": ["canonical", "clean_audio"]
    }
  ]
}
```

Tags to cover: `canonical`, `name_last`, `name_medial`, `no_name`, `fraction`,
`self_correction`, `noisy`, `multi_token_sku`, `unknown_sku`, `do_homophone`,
`spoken_price`, `no_spoken_price`.
