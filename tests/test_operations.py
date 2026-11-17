import unittest
from app.persistence import same_value
from app.catalog import validate_change
from app.domain import ValidationError

class OperationalValues(unittest.TestCase):
    def test_oracle_dates_and_decimal_formats_do_not_create_false_changes(self):
        self.assertTrue(same_value('close_date','02/12/26','2026-12-02'))
        self.assertTrue(same_value('probability','25.00','25'))
        self.assertFalse(same_value('stage','01 - Interesado','02 - Inscrito a prueba'))
    def test_only_fields_with_a_writer_and_valid_values_are_accepted(self):
        for field,value in [('campus_id','123'),('payment','Confirmado'),('probability','nan'),('close_date','31/99/00')]:
            with self.subTest(field=field),self.assertRaises(ValidationError):validate_change(field,value)

if __name__=='__main__':unittest.main()
