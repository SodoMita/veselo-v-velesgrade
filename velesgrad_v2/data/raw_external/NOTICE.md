# External data for Mira (raw, not yet ingested)

| Path | Content | Source | License |
|---|---|---|---|
| `dailydialog/` | 13k multi-turn everyday chats (train/validation/test), daily life: family, home, work, food | DailyDialog, Li et al., IJCNLP 2017 (mirror: huggingface.co/datasets/roskoN/dailydialog) | CC BY-NC-SA 4.0 (non-commercial, share-alike) |
| `gutenberg/pg2680.txt` | Marcus Aurelius, *Meditations* | Project Gutenberg #2680 | Public domain (US); Gutenberg license text inside file |
| `gutenberg/pg205.txt` | Thoreau, *Walden* and *Civil Disobedience* | Project Gutenberg #205 | Public domain (US) |
| `gutenberg/pg3600.txt` | Montaigne, *Essays* (complete) | Project Gutenberg #3600 | Public domain (US) |
| `gutenberg/pg4200.txt` | Samuel Pepys, *Diary* (complete) | Project Gutenberg #4200 | Public domain (US) |
| `opentdb/opentdb_questions.json` | 1,100 general-knowledge trivia questions (multiple/boolean) | Open Trivia Database (opentdb.com) | CC BY-SA 4.0 |

Because DailyDialog is NC, it must not be used in a commercial release of Mira
without a separate license. The Gutenberg texts and OpenTDB are unrestricted for
this project, with attribution for OpenTDB.
