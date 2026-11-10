# The script: the seven-beat What If formula

Decoded on 21 Oct 2026 from five scripts across four channels that broke out with this format in October 2026
(Ifverse, FunNotSoFun, IFinity, Could've Been Tales). The full episodes run 7 to 10 minutes and hit all seven beats;
the skill makes a 15 to 25 second episode, which is the cold open of one: beats 1 to 4 in full, 5 to 7 folded into
the last line.

## The seven beats

1. **Cold open in the middle of the action.** A flash-forward to the climax, or three or four quick demos of the
   power.
2. **The premise and its rules.** What changed overnight, and the rules it comes with.
3. **The fun part.** Escalating wins in everyday life.
4. **The not-so-fun part.** The cost, with real science and real numbers woven into the story ("That's real.").
5. **Someone powerful notices.** A man in a suit, robbers, a government.
6. **A moral choice with family at stake,** usually a little sister.
7. **Cliffhanger.** "Part 1 of 2", a question for the comments, sometimes an "is any of this real?" section and
   sourced science notes in the description.

Recurring cast: you (second person), a best friend, a little sister, mum. In our cast: Pip is "you", Mo is the best
friend, and `sis`, `mom` and `suit` are on the rig for beats 5 and 6.

## The 15 to 25 second shape

| Beat | Seconds | What it does | Example (rewind) |
|---|---|---|---|
| 1. Cold open | 0 to 11 | Three quick demos: a small everyday problem, the power, the win. The power's word is said every time. | "You knock your coffee off the desk. Rewind. You catch it." x3 |
| 2. Premise | 11 to 15 | The title card says it: "What if you could ...?", plus one rule. | "What if you could rewind ten seconds, any time you want?" |
| 3. Fun | 1 to 2 s | One line, or one more escalation. | "Sounds amazing." |
| 4 to 7. The turn | last 2 to 6 s | The cost, ideally one real fact with a number and "That's real.", then a line that leaves a question open. | "It's about to ruin your life." |

A longer cut (40 to 60 s) adds beat 4 properly (the fact, then its consequence on screen), the suit noticing (5)
and the sister in danger (6), and ends on "Part 1".

## Writing rules

- **Second person, present tense, short sentences.** Three to eight words. "Copy a cookie. Paste." beats "Imagine if
  you were able to duplicate a cookie."
- **Every line is a picture.** Each demo has to read in one shot with no text on screen: a mug, a stair, a quiz, a
  cookie, a friend. If a line needs a caption to be understood, rewrite the line.
- **The power has a word, a sound and a look.** "Rewind" plus tape whirr plus a stopwatch counting back; "Copy...
  Paste" plus a selection box plus a pop. Say the word in every demo, so the viewer learns the grammar by the third.
- **Escalate the demos.** Small and selfish, then useful, then a little uncanny (a cookie, the homework, your best
  friend). The third demo should make the viewer slightly uneasy: it sets up the turn.
- **One real fact in the turn, with a number, checked.** Work the arithmetic, write it in the episode's `science`
  field with its source, and only then put it in the script. "That's real." goes straight after it. Never invent a
  number, never round one into a different claim.
- **End on a question or a threat,** never a resolution: "So where are yours coming from?", "It's about to ruin
  your life."
- **Length:** 45 to 65 words lands at 15 to 25 seconds after voice.py tightens the pauses (about 2.7 words a
  second). Count before you call the voice: every character costs credits.
- **The title card** is the premise, in capitals: line 1 `WHAT IF YOU COULD`, line 2 the power in four words or
  fewer with a question mark. One word of line 2 can pulse as the accent (`10`, `ANYTHING`).

## Choosing a topic

- An everyday power with clear rules and a hidden cost works best: time (rewind, pause, skip), copies, senses (hear
  thoughts, see an hour ahead), body (never sleep, 10x reaction), money, luck.
- The cost should come from real science (energy, biology, physics, economics), so beat 4 can teach something true.
- Don't remake a channel's episode: search YouTube for the premise first, and if a What If channel already has that
  exact title, pick a different power or a different rule. Most everyday powers have been done somewhere (copy-paste
  turned up a comedy short and a "Copy Powers" episode); the story, the rule and the turn are what make it ours.
  The formula is shared; the stories are ours.
- No real people, no brands, no famous characters, nothing that resembles one.

## episode.json: the script part

The copy-paste example (`studio/src/episodes/copy-paste/episode.json`), 61 words, 23 s:

```json
"topic": "What if you could copy and paste anything?",
"title": ["WHAT IF YOU COULD", "COPY AND PASTE ANYTHING?"],
"script": [
  {"beat": "1 cold open, demo 1 (small and selfish)", "text": "Copy a cookie. Paste. Free cookies, forever."},
  {"beat": "1 cold open, demo 2 (useful)", "text": "Copy your homework. Paste. Done."},
  {"beat": "1 cold open, demo 3 (a little uncanny)", "text": "Copy your best friend. Paste. Okay, that's weird."},
  {"beat": "2 the premise (title card)", "text": "What if you could copy and paste anything?"},
  {"beat": "4 the turn: the cost, one real fact", "text": "One catch: a copy can't come from nothing. One cookie, made from pure energy, needs every power plant on Earth running for over ten minutes. That's real."},
  {"beat": "5-7 folded into a question", "text": "So where are yours coming from?"}
],
"science": [
  {"claim": "One cookie made from pure energy needs every power plant on Earth running for over ten minutes.",
   "working": "A 30 g cookie: E = mc^2 = 2.70e15 J. World electricity, 29,925 TWh in 2023 = 3.4e12 W on average. 2.70e15 / 3.4e12 = about 13 minutes. Over ten minutes holds above about 24 g; the schematic states the 30 g.",
   "source": "mass-energy equivalence; Ember, Global Electricity Review 2024"}
]
```

`voice.py` joins the beats' text with spaces and sends it as one take, so the read flows; the beats are for you and
for the storyboard.
