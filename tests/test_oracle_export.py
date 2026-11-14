import unittest
from app.oracle_export import parse_export
from app.domain import ValidationError
class ExportTests(unittest.TestCase):
    def test_html_export_is_decoded_deduplicated_and_whitelisted(self):
        html='<table><tr><th>Número de oportunidad</th><th>Nombre</th><th>Correo electrónico de responsable</th><th>Importe</th><th>Campo desconocido</th></tr>'+'<tr><td>SYNTHETIC-001</td><td>Ficticio &amp; Prueba</td><td>test@example.invalid</td><td>0 GTQ</td><td>descartar</td></tr>'*2+'</table>'
        result=parse_export(html,'Prueba sintética')
        self.assertEqual(len(result['records']),1);self.assertEqual(result['records'][0]['name'],'Ficticio & Prueba')
        self.assertEqual(result['records'][0]['owner_email'],'test@example.invalid');self.assertTrue(result['partial'])
        self.assertEqual(result['records'][0]['amount'],'0 GTQ');self.assertNotIn('descartar',str(result))
        self.assertEqual(result['visible_fields']['SYNTHETIC-001'],['opportunity_number','name','owner_email','amount'])
    def test_invalid_or_empty_export_is_not_a_successful_refresh(self):
        for html in ('<table></table>','<table><tr><th>Número de oportunidad</th></tr></table>'):
            with self.assertRaises(ValidationError):parse_export(html,'Prueba')
