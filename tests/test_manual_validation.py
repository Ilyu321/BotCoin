"""Manuelle Validierungstests für Phase 3 & 4 Optimierungen."""
import sys
import os

# Füge das Projekt-Root zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_syntax_validation():
    """Validiert die Syntax aller Python-Dateien."""
    import py_compile
    import glob
    
    files_to_check = [
        'src/main.py',
        'src/data_fetcher.py',
        'src/cache_manager.py',
        'src/llm_engine.py',
        'src/config.py',
        'src/risk_analyzer.py',
        'src/input_validator.py',
        'src/portfolio_tracker.py',
        'src/config_validator.py',
        'src/retry.py',
        'src/signal_handler.py'
    ]
    
    print("Validiere Syntax aller Python-Dateien...")
    errors = []
    
    for filepath in files_to_check:
        try:
            py_compile.compile(filepath, doraise=True)
            print(f"  OK: {filepath}")
        except py_compile.PyCompileError as e:
            print(f"  FEHLER: {filepath}: {e}")
            errors.append((filepath, str(e)))
    
    if errors:
        raise AssertionError(f"Syntax-Fehler in {len(errors)} Dateien: {errors}")
    
    print("Alle Syntax-Validierungen erfolgreich\n")


def test_config_constants():
    """Validiert die neuen Konfigurationskonstanten."""
    print("Validiere Konfigurationskonstanten...")
    
    # Lese config.py Datei direkt (ohne Import)
    config_path = 'src/config.py'
    with open(config_path, 'r', encoding='utf-8') as f:
        config_content = f.read()
    
    # Prompt-Optimierung Konstanten prüfen
    required_constants = [
        'PROMPT_CACHE_ENABLED',
        'PROMPT_CACHE_TTL',
        'TOKEN_OPTIMIZATION_ENABLED',
        'MAX_PROMPT_TOKENS',
        'MAX_LLM_RETRY_ATTEMPTS',
        'LLM_RETRY_BASE_DELAY',
        'LLM_RETRY_MAX_DELAY',
        'COST_AWARENESS_ENABLED',
        'MAX_ANALYST_TOKENS',
        'MAX_GUARDIAN_TOKENS'
    ]
    
    missing = []
    for const in required_constants:
        if const not in config_content:
            missing.append(const)
    
    if missing:
        raise AssertionError(f"Fehlende Konfigurationskonstanten: {missing}")
    
    print("Alle Konfigurationskonstanten vorhanden\n")


def test_imports():
    """Validiert, dass alle Python-Module existieren."""
    print("Validiere Modul-Dateien...")
    
    modules = [
        'src/config.py',
        'src/cache_manager.py',
        'src/data_fetcher.py',
        'src/risk_analyzer.py',
        'src/llm_engine.py',
        'src/input_validator.py',
        'src/main.py'
    ]
    
    for module in modules:
        if not os.path.exists(module):
            raise AssertionError(f"Modul-Datei nicht gefunden: {module}")
        print(f"  OK: {module}")
    
    print("Alle Modul-Dateien vorhanden\n")


def test_prompt_files():
    """Validiert die Prompt-Dateien."""
    print("Validiere Prompt-Dateien...")
    
    prompt_files = [
        'src/prompts/1_analyst.j2',
        'src/prompts/2_guardian.j2'
    ]
    
    for filepath in prompt_files:
        if not os.path.exists(filepath):
            raise AssertionError(f"Prompt-Datei nicht gefunden: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Grundlegende Struktur prüfen
            if '<role>' not in content:
                raise AssertionError(f"{filepath}: Fehlendes <role> Tag")
            if '<task>' not in content:
                raise AssertionError(f"{filepath}: Fehlendes <task> Tag")
            # Optimierte Prompts verwenden <input> statt <context>
            if '<context>' not in content and '<input>' not in content:
                raise AssertionError(f"{filepath}: Fehlendes <context> oder <input> Tag")
            # Optimierte Prompts verwenden <validation> statt <rules>
            if '<rules>' not in content and '<validation>' not in content:
                raise AssertionError(f"{filepath}: Fehlendes <rules> oder <validation> Tag")
            if '<output>' not in content:
                raise AssertionError(f"{filepath}: Fehlendes <output> Tag")
            
            # Optimierte Version prüfen (kürzer, strukturierter)
            lines = content.strip().split('\n')
            # Optimierte Prompts sollten weniger Zeilen haben
            assert len(lines) < 120, f"{filepath}: Prompt ist zu lang ({len(lines)} Zeilen)"
            
        print(f"  OK: {filepath} ({(len(content))} Zeichen)")
    
    print("Alle Prompt-Dateien valide\n")


def test_removed_features():
    """Validiert, dass entfernte Features nicht mehr vorhanden sind."""
    print("Validiere Entfernung der dynamischen Admin-ID...")
    
    # Prüfe main.py auf entfernte Funktionen
    main_path = 'src/main.py'
    with open(main_path, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    if 'cmd_set_admin' in main_content:
        raise AssertionError("cmd_set_admin sollte entfernt worden sein")
    if 'load_admin_id' in main_content:
        raise AssertionError("load_admin_id sollte entfernt worden sein")
    if 'CONFIG_OVERRIDE_PATH' in main_content:
        raise AssertionError("CONFIG_OVERRIDE_PATH sollte entfernt worden sein")
    
    # Prüfe input_validator.py auf entfernte Funktionen
    validator_path = 'src/input_validator.py'
    with open(validator_path, 'r', encoding='utf-8') as f:
        validator_content = f.read()
    
    if 'validate_set_admin_args' in validator_content:
        raise AssertionError("validate_set_admin_args sollte entfernt worden sein")
    if 'SetAdminRequest' in validator_content:
        raise AssertionError("SetAdminRequest sollte entfernt worden sein")
    
    print("Dynamische Admin-ID erfolgreich entfernt\n")


def run_all_tests():
    """Führt alle manuellen Tests aus."""
    print("=" * 60)
    print("BotCoin Phase 3 & 4 Validierungstests")
    print("=" * 60 + "\n")
    
    try:
        test_syntax_validation()
        test_config_constants()
        test_imports()
        test_prompt_files()
        test_removed_features()
        
        print("=" * 60)
        print("Alle Validierungstests erfolgreich abgeschlossen!")
        print("=" * 60)
        return True
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"Test fehlgeschlagen: {e}")
        print("=" * 60)
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)