import pytest
from maas.routing import resolve_plan, validate_selection

CONTEXT = {'order_id': 'order', 'providers': ['transport', 'parking', 'bike']}

@pytest.mark.parametrize('question,intent,target,providers', [
 ('Peux-tu me donner le tarif du parking ?', 'tariff', 'tariffs', ['parking']),
 ('Quelle commission pour le Parking ?', 'clearing', 'clearing', ['parking']),
 ('Le vélo ne se déverrouille pas', 'sav', 'sav', ['bike']),
 ('Y a-t-il une place au parking ?', 'availability', 'mobility', ['parking']),
 ('Prépare une proposition transport et parking', 'offer', 'mobility', ['transport','parking']),
 ('Mes mensualités du compte mobilité', 'account', 'history', []),
 ('Tarif abonnement annuel transport', 'tariff', 'tariffs', ['transport']),
 ('Quels sont les achats de Léa ?', 'history', 'history', []),
 ('Vérifie les preuves blockchain de mon achat', 'verification', 'history', []),
 ('La répartition par fournisseur de ma commande', 'clearing', 'clearing', CONTEXT['providers']),
 ('La commission parking, pas le transport ni le vélo', 'clearing', 'clearing', ['parking']),
 ('Commissions de tous les fournisseurs sauf le vélo', 'clearing', 'clearing', ['transport','parking']),
])
def test_explicit_request_scope(question,intent,target,providers):
 p=resolve_plan(question, CONTEXT)
 assert not p.get('clarification')
 assert (p['intent'],p['target'],p['providers'])==(intent,target,providers)

@pytest.mark.parametrize('question', ['Pourquoi ?', 'Quel est le tarif ?', 'Quelle commission ?'])
def test_ambiguous_request_never_fans_out(question):
 p=resolve_plan(question, CONTEXT)
 assert p.get('clarification')
 with pytest.raises(ValueError): validate_selection(p,'clearing',[],'alize')

def test_empty_model_selection_is_limited_to_actual_request():
 p=resolve_plan('La commission parking',CONTEXT)
 assert validate_selection(p,'clearing',[],'alize')==['parking']
 with pytest.raises(ValueError): validate_selection(p,'clearing',['bike'],'alize')
 with pytest.raises(ValueError): validate_selection(p,'sav',['parking'],'alize')

def test_transport_has_no_stock_availability_capability():
 assert resolve_plan('Disponibilité transport',CONTEXT).get('clarification')

def test_service_outside_selected_order_is_not_called():
 assert resolve_plan('Incident vélo',{'order_id':'x','providers':['parking']}).get('clarification')
