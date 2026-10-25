from maas.knowledge import lexical_vector, terms


def test_accents_and_query_operators_are_normalized():
    assert terms("Étudiant | PARKING* (vélo)") == ["etudiant", "parking", "velo"]


def test_empty_words_do_not_create_zero_vector_query():
    assert lexical_vector("les des une") is None


def test_word_vector_has_expected_geometry():
    a = lexical_vector("étudiant")
    b = lexical_vector("ETUDIANT")
    assert a == b and sum(v * v for v in a) == 1.0
    assert len(a) == 96
