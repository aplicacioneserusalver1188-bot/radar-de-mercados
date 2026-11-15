#!/usr/bin/env python3
"""Instala únicamente el modelo inglés-español de Argos Translate (software gratuito)."""
from argostranslate import package, translate

def main():
    installed=translate.get_installed_languages()
    english=next((x for x in installed if x.code=="en"),None)
    spanish=next((x for x in installed if x.code=="es"),None)
    if english and spanish and english.get_translation(spanish):
        print("Modelo en-es ya instalado")
        return
    package.update_package_index()
    matches=[p for p in package.get_available_packages()
             if p.from_code=="en" and p.to_code=="es" and p.type=="translate"]
    if not matches:
        raise SystemExit("Modelo Argos en-es no disponible; no se inventan traducciones")
    chosen=matches[-1]
    package.install_from_path(chosen.download())
    print("Modelo en-es instalado para traducción local sin API")

if __name__=="__main__": main()
