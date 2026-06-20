#!/usr/bin/env python3
"""Generate a templated Portuguese grammatical minimal-pair benchmark.

Each item is a (grammatical, ungrammatical) pair differing by exactly ONE targeted morphological
feature, labelled by phenomenon. Vocabulary is simple/high-frequency (TinyStories-scale) and uses only
REGULAR morphology (vowel-final nouns with -s plurals; -o/-a adjectives; regular present-tense verbs),
so every "ungrammatical" member is provably ungrammatical with no irregular-form pitfalls.

Output: data/eval/pt_minimal_pairs.jsonl  (+ a .sha256 next to it for immutability).
Scored downstream by the log-prob margin: margin = logprob(grammatical) - logprob(ungrammatical);
the model is "correct" on an item when margin > 0.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "eval" / "pt_minimal_pairs.jsonl"
PER_PHENOMENON = 60
SEED = 20260620

# (singular, plural, gender) — all vowel-final with regular -s plurals, common/simple vocabulary.
NOUNS = [
    ("gato", "gatos", "m"), ("cachorro", "cachorros", "m"), ("livro", "livros", "m"),
    ("carro", "carros", "m"), ("menino", "meninos", "m"), ("amigo", "amigos", "m"),
    ("prato", "pratos", "m"), ("sapato", "sapatos", "m"), ("copo", "copos", "m"),
    ("barco", "barcos", "m"), ("quarto", "quartos", "m"), ("pássaro", "pássaros", "m"),
    ("pato", "patos", "m"), ("rato", "ratos", "m"), ("bolo", "bolos", "m"),
    ("lobo", "lobos", "m"), ("ovo", "ovos", "m"), ("galo", "galos", "m"),
    ("sapo", "sapos", "m"), ("vaso", "vasos", "m"), ("pano", "panos", "m"),
    ("dado", "dados", "m"), ("tijolo", "tijolos", "m"), ("espelho", "espelhos", "m"),
    ("casa", "casas", "f"), ("mesa", "mesas", "f"), ("porta", "portas", "f"),
    ("menina", "meninas", "f"), ("amiga", "amigas", "f"), ("cadeira", "cadeiras", "f"),
    ("janela", "janelas", "f"), ("bola", "bolas", "f"), ("caneta", "canetas", "f"),
    ("fruta", "frutas", "f"), ("camisa", "camisas", "f"), ("escola", "escolas", "f"),
    ("vaca", "vacas", "f"), ("gata", "gatas", "f"), ("pata", "patas", "f"),
    ("fita", "fitas", "f"), ("capa", "capas", "f"), ("sopa", "sopas", "f"),
    ("uva", "uvas", "f"), ("rosa", "rosas", "f"), ("vela", "velas", "f"),
    ("boneca", "bonecas", "f"), ("tartaruga", "tartarugas", "f"), ("caixa", "caixas", "f"),
]
# adjective forms: m_sg, f_sg, m_pl, f_pl  (regular -o/-a/-os/-as)
ADJS = [
    ("bonito", "bonita", "bonitos", "bonitas"), ("pequeno", "pequena", "pequenos", "pequenas"),
    ("alto", "alta", "altos", "altas"), ("novo", "nova", "novos", "novas"),
    ("velho", "velha", "velhos", "velhas"), ("branco", "branca", "brancos", "brancas"),
    ("vermelho", "vermelha", "vermelhos", "vermelhas"), ("amarelo", "amarela", "amarelos", "amarelas"),
    ("gordo", "gorda", "gordos", "gordas"), ("magro", "magra", "magros", "magras"),
    ("limpo", "limpa", "limpos", "limpas"), ("molhado", "molhada", "molhados", "molhadas"),
]
# present-tense, intransitive, regular: (3sg, 3pl)
VERBS = [
    ("dorme", "dormem"), ("corre", "correm"), ("pula", "pulam"), ("anda", "andam"),
    ("canta", "cantam"), ("nada", "nadam"), ("voa", "voam"), ("brinca", "brincam"),
    ("chora", "choram"), ("sobe", "sobem"), ("trabalha", "trabalham"), ("descansa", "descansam"),
]
DEF = {("m", "sg"): "o", ("f", "sg"): "a", ("m", "pl"): "os", ("f", "pl"): "as"}
INDEF = {("m", "sg"): "um", ("f", "sg"): "uma", ("m", "pl"): "uns", ("f", "pl"): "umas"}
DEM = {  # demonstrative "este" family
    ("m", "sg"): "este", ("f", "sg"): "esta", ("m", "pl"): "estes", ("f", "pl"): "estas",
}


def cap(s: str) -> str:
    return s[0].upper() + s[1:]


def build(rng: random.Random):
    items = []

    def add(phen, gram, ungram, gender, number):
        items.append({"phenomenon": phen, "grammatical": gram, "ungrammatical": ungram,
                      "gender": gender, "number": number})

    def nouns_shuf():
        ns = NOUNS[:]; rng.shuffle(ns); return ns

    # 1. article_noun_gender — flip definite article gender (singular)
    for sg, _pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        wrong = "o" if g == "f" else "a"
        add("article_noun_gender", f"Eu vejo {DEF[(g,'sg')]} {sg}.", f"Eu vejo {wrong} {sg}.", g, "sg")

    # 2. article_noun_number — plural noun, singular article (flip article number)
    for sg, pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        add("article_noun_number", f"Eu vejo {DEF[(g,'pl')]} {pl}.", f"Eu vejo {DEF[(g,'sg')]} {pl}.", g, "pl")

    # 3. adjective_noun_gender — flip adjective gender
    for (sg, _pl, g) in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        m, f, _, _ = rng.choice(ADJS)
        good, bad = (m, f) if g == "m" else (f, m)
        add("adjective_noun_gender", f"Eu vejo {DEF[(g,'sg')]} {sg} {good}.",
            f"Eu vejo {DEF[(g,'sg')]} {sg} {bad}.", g, "sg")

    # 4. adjective_noun_number — plural NP, flip adjective number
    for (sg, pl, g) in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        m, f, mp, fp = rng.choice(ADJS)
        good, bad = (mp, m) if g == "m" else (fp, f)
        add("adjective_noun_number", f"Eu vejo {DEF[(g,'pl')]} {pl} {good}.",
            f"Eu vejo {DEF[(g,'pl')]} {pl} {bad}.", g, "pl")

    # 5. subject_verb_number — flip verb number (half sg-subj, half pl-subj)
    pool = (nouns_shuf() * 3)[:PER_PHENOMENON]
    for i, (sg, pl, g) in enumerate(pool):
        v_sg, v_pl = rng.choice(VERBS)
        if i % 2 == 0:  # singular subject; ungrammatical = plural verb
            add("subject_verb_number", cap(f"{DEF[(g,'sg')]} {sg} {v_sg}."), cap(f"{DEF[(g,'sg')]} {sg} {v_pl}."), g, "sg")
        else:           # plural subject; ungrammatical = singular verb
            add("subject_verb_number", cap(f"{DEF[(g,'pl')]} {pl} {v_pl}."), cap(f"{DEF[(g,'pl')]} {pl} {v_sg}."), g, "pl")

    # 6. demonstrative_gender — flip demonstrative gender (singular)
    for sg, _pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        wrong = DEM[("m", "sg")] if g == "f" else DEM[("f", "sg")]
        add("demonstrative_gender", f"Eu quero {DEM[(g,'sg')]} {sg}.", f"Eu quero {wrong} {sg}.", g, "sg")

    # 7. demonstrative_number — plural noun, singular demonstrative
    for sg, pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        add("demonstrative_number", f"Eu quero {DEM[(g,'pl')]} {pl}.", f"Eu quero {DEM[(g,'sg')]} {pl}.", g, "pl")

    # 8. indefinite_article_gender — flip indefinite article gender (singular)
    for sg, _pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        wrong = INDEF[("m", "sg")] if g == "f" else INDEF[("f", "sg")]
        add("indefinite_article_gender", f"Eu tenho {INDEF[(g,'sg')]} {sg}.", f"Eu tenho {wrong} {sg}.", g, "sg")

    # 9. predicative_adjective_gender — copula "ser", flip predicate adj gender
    for sg, _pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        m, f, _, _ = rng.choice(ADJS)
        good, bad = (m, f) if g == "m" else (f, m)
        add("predicative_adjective_gender", cap(f"{DEF[(g,'sg')]} {sg} é {good}."), cap(f"{DEF[(g,'sg')]} {sg} é {bad}."), g, "sg")

    # 10. predicative_adjective_number — copula "ser" plural, flip predicate adj number
    for sg, pl, g in (nouns_shuf() * 3)[:PER_PHENOMENON]:
        m, f, mp, fp = rng.choice(ADJS)
        good, bad = (mp, m) if g == "m" else (fp, f)
        add("predicative_adjective_number", cap(f"{DEF[(g,'pl')]} {pl} são {good}."), cap(f"{DEF[(g,'pl')]} {pl} são {bad}."), g, "pl")

    return items


def main():
    rng = random.Random(SEED)
    items = build(rng)
    # dedupe + sanity checks
    seen, clean = set(), []
    for it in items:
        assert it["grammatical"] != it["ungrammatical"], it
        gw, uw = it["grammatical"].split(), it["ungrammatical"].split()
        assert len(gw) == len(uw) and sum(a != b for a, b in zip(gw, uw)) == 1, ("not single-token edit", it)
        key = (it["grammatical"], it["ungrammatical"])
        if key in seen:
            continue
        seen.add(key)
        it["id"] = len(clean) + 1
        clean.append(it)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in clean)
    OUT.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    OUT.with_suffix(".jsonl.sha256").write_text(digest + "\n", encoding="utf-8")
    # report
    from collections import Counter
    c = Counter(it["phenomenon"] for it in clean)
    print(f"wrote {len(clean)} pairs to {OUT}")
    print("sha256:", digest)
    print("by phenomenon:", dict(c))


if __name__ == "__main__":
    main()
