"""Fictional vocabularies every generated text value is composed from
(RNF-07).

These are **invented tokens**, not a sample of any real register, roll,
census or name list. They read as plausible Portuguese so a demo does not
look like a lorem-ipsum dump, but no value here identifies a real person, and
nothing generated from them can. The closed-vocabulary shape is what makes
that claim testable rather than asserted: `test_synthetic_generation.py`
decomposes every generated name and fails if any part is not declared here.

Two further rules hold across the whole file:

- **No digits, no `@`.** A generated text value must never be mistakable for
  a CPF, an enrollment number, a phone or an e-mail. That is why classrooms
  are named "Turma Aurora" rather than "6º Ano A" — the familiar Brazilian
  form carries a digit and would fail the no-real-data scan for a cosmetic
  reason.
- **Composition is a pure index decode**, so the caller (`population.py`)
  owns *which* index each student gets and this module owns only *how* an
  index becomes a name.
"""

from __future__ import annotations

#: 24 invented given names.
GIVEN_NAMES: tuple[str, ...] = (
    "Amarilis",
    "Belarmino",
    "Cassiana",
    "Delmiro",
    "Elviria",
    "Fanuel",
    "Gilvana",
    "Heliodoro",
    "Ivanira",
    "Jandira",
    "Kelmar",
    "Luciola",
    "Marcenil",
    "Nivaldina",
    "Orlandir",
    "Petronila",
    "Quirino",
    "Rosalvo",
    "Sandoval",
    "Teolinda",
    "Ubirandir",
    "Valquiria",
    "Wanderlino",
    "Zilmara",
)

#: 18 invented first surnames.
FIRST_SURNAMES: tuple[str, ...] = (
    "Alvenar",
    "Brandel",
    "Corvelo",
    "Dantena",
    "Estivar",
    "Farelim",
    "Guarnel",
    "Hortenar",
    "Idalvo",
    "Juremar",
    "Lamerce",
    "Marvelo",
    "Nortena",
    "Orvalhes",
    "Pindara",
    "Quirandel",
    "Ravenal",
    "Solmar",
)

#: 15 invented second surnames.
SECOND_SURNAMES: tuple[str, ...] = (
    "Tavanor",
    "Urbena",
    "Valdares",
    "Ximeno",
    "Zandel",
    "Arvorel",
    "Belmirar",
    "Cerqueda",
    "Duvante",
    "Encantel",
    "Fiorela",
    "Golvane",
    "Iracemo",
    "Lunares",
    "Mirantel",
)

#: 24 * 18 * 15 = 6480 distinct names — comfortably above the ~200-student
#: base, so the mixed-radix decode below never has to wrap.
NAME_CAPACITY: int = len(GIVEN_NAMES) * len(FIRST_SURNAMES) * len(SECOND_SURNAMES)

#: Invented classroom labels. Deliberately not "6º Ano A": see the no-digits
#: rule in the module docstring.
CLASSROOM_LABELS: tuple[str, ...] = (
    "Aurora",
    "Boreal",
    "Cristal",
    "Dunas",
    "Esmeralda",
    "Farol",
    "Girassol",
    "Horizonte",
    "Iracema",
    "Jasmim",
    "Lumiar",
    "Miragem",
    "Nevoa",
    "Orvalho",
    "Perola",
    "Quartzo",
    "Regata",
    "Sereno",
    "Trilha",
    "Umbral",
    "Vertente",
    "Xisto",
    "Zenite",
)

CLASSROOM_NAME_TEMPLATE = "Turma {label}"


def compose_name(index: int) -> str:
    """Decode `index` into `"<given> <first surname> <second surname>"`.

    Mixed-radix over the three vocabularies, which makes the decode a
    *bijection* on `range(NAME_CAPACITY)`: distinct indices can never collide
    on the same full name, so the caller gets uniqueness for free without a
    retry loop (and without the retry loop's order sensitivity).
    """
    if not 0 <= index < NAME_CAPACITY:
        raise ValueError(f"name index {index} outside 0..{NAME_CAPACITY - 1}")

    given_index = index % len(GIVEN_NAMES)
    rest = index // len(GIVEN_NAMES)
    first_index = rest % len(FIRST_SURNAMES)
    second_index = rest // len(FIRST_SURNAMES)

    return (
        f"{GIVEN_NAMES[given_index]} "
        f"{FIRST_SURNAMES[first_index]} "
        f"{SECOND_SURNAMES[second_index]}"
    )


def compose_classroom_name(index: int) -> str:
    """Decode `index` into `"Turma <label>"`.

    Bijective base-N over `CLASSROOM_LABELS` (the spreadsheet-column scheme:
    ... Zenite, Aurora Aurora, Aurora Boreal ...), so *any* classroom count is
    nameable without collision — `classrooms.name` carries a UNIQUE
    constraint, and a generator that could run out of names at high volume
    would fail as an IntegrityError deep inside a flush instead of not
    failing at all.
    """
    if index < 0:
        raise ValueError(f"classroom index {index} must be non-negative")

    radix = len(CLASSROOM_LABELS)
    parts: list[str] = []
    value = index
    while True:
        parts.append(CLASSROOM_LABELS[value % radix])
        value = value // radix - 1
        if value < 0:
            break

    return CLASSROOM_NAME_TEMPLATE.format(label=" ".join(reversed(parts)))
