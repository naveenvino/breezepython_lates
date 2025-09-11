from src.services.kite_option_chain_service import get_kite_option_chain_service

service = get_kite_option_chain_service()

strikes = [24700, 24750, 24800, 24850, 24900, 24950, 25000, 25050, 25100, 25150, 25200]

print("Testing Kite quotes for all strikes:")
print("-" * 50)

for strike in strikes:
    ce = service.get_option_quote(strike, 'CE', '2025-09-16')
    pe = service.get_option_quote(strike, 'PE', '2025-09-16')
    print(f'{strike}: CE={ce.get("ltp", 0):.2f}, PE={pe.get("ltp", 0):.2f}')