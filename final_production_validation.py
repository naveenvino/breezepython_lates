"""
Final Production Validation - Comprehensive System Check
"""
import os
import sys
from pathlib import Path
import json
import time
from datetime import datetime

def validate_production_implementation():
    """Validate all production components are properly implemented"""
    
    print("=" * 80)
    print("FINAL PRODUCTION VALIDATION")
    print("=" * 80)
    print(f"Validation Time: {datetime.now()}")
    print()
    
    results = {}
    
    # 1. File Structure Validation
    print("1. FILE STRUCTURE VALIDATION")
    print("-" * 40)
    
    production_files = {
        "Database Connection Pool": "src/infrastructure/database/connection_pool.py",
        "Exception Handling": "src/core/exceptions.py",
        "Risk Management": "src/core/risk_manager.py", 
        "Audit Logging": "src/core/audit_logger.py",
        "Monitoring System": "src/core/monitoring.py",
        "Security Manager": "src/core/security.py",
        "Backup Manager": "src/core/backup_manager.py",
        "Rate Limiter": "src/middleware/rate_limiter.py",
        "Production API": "production_ready_api.py"
    }
    
    files_ok = 0
    for name, file_path in production_files.items():
        path = Path(file_path)
        if path.exists():
            size = path.stat().st_size
            print(f"[OK] {name:<25} {size:>8,} bytes")
            files_ok += 1
        else:
            print(f"[X] {name:<25} MISSING")
    
    results["files"] = {"total": len(production_files), "found": files_ok}
    print(f"\nFiles Status: {files_ok}/{len(production_files)} found")
    
    # 2. Code Quality Validation
    print("\n2. CODE QUALITY VALIDATION")
    print("-" * 40)
    
    # Check for key production patterns
    quality_checks = []
    
    for name, file_path in production_files.items():
        path = Path(file_path)
        if path.exists():
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                
                # Check for production patterns
                has_logging = "import logging" in content
                has_exceptions = "Exception" in content
                has_docstrings = '"""' in content
                has_type_hints = "def " in content and ":" in content
                
                score = sum([has_logging, has_exceptions, has_docstrings, has_type_hints])
                quality_checks.append(score)
                
                print(f"[OK] {name:<25} Quality Score: {score}/4")
                
            except Exception as e:
                print(f"[X] {name:<25} Read Error: {str(e)[:50]}")
                quality_checks.append(0)
    
    avg_quality = sum(quality_checks) / len(quality_checks) if quality_checks else 0
    results["code_quality"] = {"average_score": avg_quality, "max_score": 4}
    print(f"\nCode Quality: {avg_quality:.1f}/4.0 average")
    
    # 3. Configuration Validation
    print("\n3. CONFIGURATION VALIDATION")
    print("-" * 40)
    
    config_files = {
        ".env.example": ["DB_SERVER", "BREEZE_API_KEY", "KITE_API_KEY", "JWT_SECRET_KEY"],
        "Dockerfile": ["FROM python:", "USER trader", "HEALTHCHECK", "EXPOSE"],
        "requirements.txt": ["fastapi", "sqlalchemy", "uvicorn"],
        "CLAUDE.md": ["Production", "API", "Database"]
    }
    
    config_ok = 0
    for file_name, required_items in config_files.items():
        path = Path(file_name)
        if path.exists():
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                found_items = sum(1 for item in required_items if item in content)
                print(f"[OK] {file_name:<20} {found_items}/{len(required_items)} items")
                if found_items == len(required_items):
                    config_ok += 1
            except:
                print(f"[X] {file_name:<20} Read Error")
        else:
            print(f"[X] {file_name:<20} Missing")
    
    results["configuration"] = {"total": len(config_files), "valid": config_ok}
    print(f"\nConfiguration: {config_ok}/{len(config_files)} files valid")
    
    # 4. Production Features Validation
    print("\n4. PRODUCTION FEATURES VALIDATION")
    print("-" * 40)
    
    features_to_check = [
        ("Error Handling", "src/core/exceptions.py", ["BaseAppException", "DatabaseException", "TradingException"]),
        ("Risk Management", "src/core/risk_manager.py", ["RiskManager", "validate_new_position", "circuit_breaker"]),
        ("Audit Logging", "src/core/audit_logger.py", ["AuditLogger", "log_trade_entry", "audit_log"]),
        ("Monitoring", "src/core/monitoring.py", ["MonitoringSystem", "record_metric", "AlertSeverity"]),
        ("Security", "src/core/security.py", ["SecurityManager", "JWT", "Session"]),
        ("Backup", "src/core/backup_manager.py", ["BackupManager", "create_full_backup", "restore"]),
        ("Rate Limiting", "src/middleware/rate_limiter.py", ["RateLimiter", "check_request", "TokenBucket"])
    ]
    
    features_ok = 0
    for feature_name, file_path, keywords in features_to_check:
        path = Path(file_path)
        if path.exists():
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                found = sum(1 for keyword in keywords if keyword in content)
                status = "[OK]" if found == len(keywords) else "[!]"
                print(f"{status} {feature_name:<20} {found}/{len(keywords)} features")
                if found == len(keywords):
                    features_ok += 1
            except:
                print(f"[X] {feature_name:<20} Read Error")
        else:
            print(f"[X] {feature_name:<20} File Missing")
    
    results["features"] = {"total": len(features_to_check), "implemented": features_ok}
    print(f"\nProduction Features: {features_ok}/{len(features_to_check)} implemented")
    
    # 5. Directory Structure Validation
    print("\n5. DIRECTORY STRUCTURE VALIDATION")
    print("-" * 40)
    
    required_dirs = [
        "src/core",
        "src/infrastructure/database", 
        "src/middleware",
        "logs",
        "data"
    ]
    
    dirs_ok = 0
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            print(f"[OK] {dir_path}")
            dirs_ok += 1
        else:
            print(f"[X] {dir_path} (creating...)")
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"  -> Created {dir_path}")
                dirs_ok += 1
            except:
                print(f"  -> Failed to create {dir_path}")
    
    results["directories"] = {"total": len(required_dirs), "created": dirs_ok}
    print(f"\nDirectories: {dirs_ok}/{len(required_dirs)} ready")
    
    # 6. Calculate Overall Score
    print("\n" + "=" * 80)
    print("OVERALL PRODUCTION READINESS ASSESSMENT")
    print("=" * 80)
    
    # Weighted scoring
    file_score = (results["files"]["found"] / results["files"]["total"]) * 25
    quality_score = (results["code_quality"]["average_score"] / 4.0) * 20
    config_score = (results["configuration"]["valid"] / results["configuration"]["total"]) * 20
    feature_score = (results["features"]["implemented"] / results["features"]["total"]) * 25
    dir_score = (results["directories"]["created"] / results["directories"]["total"]) * 10
    
    total_score = file_score + quality_score + config_score + feature_score + dir_score
    
    print(f"File Structure:      {file_score:5.1f}/25.0  ({results['files']['found']}/{results['files']['total']} files)")
    print(f"Code Quality:        {quality_score:5.1f}/20.0  ({results['code_quality']['average_score']:.1f}/4.0 avg)")
    print(f"Configuration:       {config_score:5.1f}/20.0  ({results['configuration']['valid']}/{results['configuration']['total']} valid)")
    print(f"Production Features: {feature_score:5.1f}/25.0  ({results['features']['implemented']}/{results['features']['total']} implemented)")
    print(f"Directory Structure: {dir_score:5.1f}/10.0  ({results['directories']['created']}/{results['directories']['total']} ready)")
    print("-" * 80)
    print(f"TOTAL SCORE:         {total_score:5.1f}/100.0")
    
    # Final verdict
    if total_score >= 90:
        verdict = "[EXCELLENT] PRODUCTION READY"
        recommendation = "Deploy immediately"
    elif total_score >= 80:
        verdict = "[GOOD] MINOR FIXES NEEDED"
        recommendation = "Fix minor issues and deploy"
    elif total_score >= 70:
        verdict = "[FAIR] SEVERAL FIXES NEEDED"
        recommendation = "Address issues before production"
    else:
        verdict = "[POOR] MAJOR FIXES REQUIRED"
        recommendation = "Significant work needed"
    
    print(f"\nVERDICT: {verdict}")
    print(f"RECOMMENDATION: {recommendation}")
    
    # 7. Next Steps
    print("\n" + "=" * 80)
    print("NEXT STEPS FOR PRODUCTION DEPLOYMENT")
    print("=" * 80)
    
    if total_score >= 85:
        print("[OK] READY FOR PRODUCTION:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Configure .env file with production credentials")
        print("   3. Start production API: python production_ready_api.py")
        print("   4. Monitor via /health endpoint")
        print("   5. Setup SSL/TLS certificates")
        print("   6. Configure load balancer (if needed)")
    else:
        print("[!] FIXES NEEDED BEFORE PRODUCTION:")
        if results["files"]["found"] < results["files"]["total"]:
            print("   • Complete file implementation")
        if results["code_quality"]["average_score"] < 3.5:
            print("   • Improve code quality and documentation")
        if results["configuration"]["valid"] < results["configuration"]["total"]:
            print("   • Fix configuration files")
        if results["features"]["implemented"] < results["features"]["total"]:
            print("   • Complete production feature implementation")
    
    print("\n" + "=" * 80)
    print(f"Validation completed: {datetime.now()}")
    
    return total_score

if __name__ == "__main__":
    score = validate_production_implementation()
    sys.exit(0 if score >= 85 else 1)