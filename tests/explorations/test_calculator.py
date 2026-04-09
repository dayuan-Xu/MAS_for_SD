from tests.explorations.caculator import Calculator


class TestCalculator:
    def setup_method(self):
        self.calculator = Calculator()

    def test_add(self):
        result = self.calculator.add(2, 3)
        assert result == 5

    def test_subtract(self):
        result = self.calculator.subtract(5, 3)
        assert result == 2
