import os
import subprocess
import shutil
import sys
import tempfile
import urllib.request
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox

# ==============================================================================
# 🎛️ CONFIGURATION VISUELLE DES SOUS-TITRES (Modifiez les valeurs ici)
# ==============================================================================
TAILLE_POLICE  = 16      # Taille du texte à l'écran
TAILLE_CONTOUR = 1.5     # Épaisseur du contour noir autour des lettres
TAILLE_OMBRE   = 1.5     # Épaisseur de l'ombre portée (mettez 0.0 pour la couper)
# ==============================================================================

# --- ÉTAPE AUTOMATIQUE : INSTALLATION DE PYSUBS2 SI MANQUANT ---
try:
    import pysubs2
    from pysubs2 import SSAFile, SSAStyle, Color
except ImportError:
    print("📦 Extension 'pysubs2' manquante. Installation automatique en cours...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pysubs2"])
        import pysubs2
        from pysubs2 import SSAFile, SSAStyle, Color
        print("✅ Extension 'pysubs2' installée avec succès !\n")
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Échec de l'installation", 
            f"Impossible d'installer automatiquement l'extension requise 'pysubs2'.\n\nErreur : {str(e)}"
        )
        sys.exit(1)


def verifier_ffmpeg():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("\nERREUR : FFmpeg ou FFprobe est introuvable. Veuillez l'installer.")
        return False
    return True


def garantir_mkvmerge():
    """Vérifie si mkvmerge est présent, sinon télécharge une version portable proprement."""
    depuis_path = shutil.which("mkvmerge")
    if depuis_path:
        return depuis_path

    chemins_standards = [
        r"C:\Program Files\MKVToolNix\mkvmerge.exe",
        r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"
    ]
    for chemin in chemins_standards:
        if os.path.exists(chemin):
            return chemin

    # Si introuvable, téléchargement d'une version portable épurée pour Windows (via les dépôts officiels/miroirs fiables)
    dossier_script = os.path.dirname(os.path.abspath(__file__))
    mkvmerge_local = os.path.join(dossier_script, "mkvmerge.exe")
    
    if os.path.exists(mkvmerge_local):
        return mkvmerge_local

    print("🌐 'mkvmerge' absent. Téléchargement automatique d'un binaire portable sécurisé...")
    url_mkvmerge = "https://mkvtoolnix.download"
    zip_temp = os.path.join(tempfile.gettempdir(), "mkvtoolnix.zip")
    dir_extract = os.path.join(tempfile.gettempdir(), "mkvtoolnix_temp")

    try:
        urllib.request.urlretrieve(url_mkvmerge, zip_temp)
        with zipfile.ZipFile(zip_temp, 'r') as zip_ref:
            zip_ref.extractall(dir_extract)
        
        # Récupère juste l'exécutable mkvmerge principal pour l'amener à côté du script
        exe_src = os.path.join(dir_extract, "mkvtoolnix", "mkvmerge.exe")
        if os.path.exists(exe_src):
            shutil.copy(exe_src, mkvmerge_local)
            print("✅ 'mkvmerge' configuré avec succès.\n")
            return mkvmerge_local
    except Exception as e:
        print(f"❌ Impossible de télécharger mkvmerge automatiquement : {e}")
    
    return None


def trouver_piste_dialogues_fr(video_entree):
    """Analyse les pistes avec ffprobe pour cibler la piste 'FR Full' ou 'Français'."""
    try:
        import json
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index:stream_tags=title,language', '-of', 'json', video_entree]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        
        if 'streams' in data:
            for i, stream in enumerate(data['streams']):
                title = stream.get('tags', {}).get('title', '').lower()
                lang = stream.get('tags', {}).get('language', '').lower()
                if ('fre' in lang or 'fra' in lang) and 'full' in title:
                    return f"0:s:{i}"
            
            for i, stream in enumerate(data['streams']):
                title = stream.get('tags', {}).get('title', '').lower()
                lang = stream.get('tags', {}).get('language', '').lower()
                if ('fre' in lang or 'fra' in lang) and 'forced' not in title:
                    return f"0:s:{i}"
    except Exception:
        pass
    return "0:s:1"


def modifier_et_reintegrer_mkv(video_entree, dossier_sortie, chemin_mkvmerge):
    with tempfile.TemporaryDirectory() as dir_temp:
        srt_temp = os.path.join(dir_temp, "temp_extract.srt")
        ass_temp = os.path.join(dir_temp, "temp_stylise.ass")
        
        nom_complet_video = os.path.basename(video_entree)
        nom_base_video, _ = os.path.splitext(nom_complet_video)
        
        nom_fichier_auto = f"{nom_base_video}.ass"
        ass_automatique = os.path.join(dossier_sortie, nom_fichier_auto)
        
        nom_fichier_lisible = f"{nom_base_video}-Francais-Lisible.ass"
        ass_lisible = os.path.join(dossier_sortie, nom_fichier_lisible)
        
        nom_video_sortie = f"{nom_base_video}_sous_titres.mkv"
        video_sortie = os.path.join(dossier_sortie, nom_video_sortie)
        
        piste_cible = trouver_piste_dialogues_fr(video_entree)
        
        try:
            # 1. Extraction via ffmpeg
            print(f"   -> Étape 1/3 : Extraction des dialogues ({piste_cible})...")
            res = subprocess.run([
                'ffmpeg', '-y', '-hide_banner', '-i', video_entree, 
                '-map', piste_cible, srt_temp
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if res.returncode != 0 or not os.path.exists(srt_temp) or os.path.getsize(srt_temp) == 0:
                return False, "Impossible d'extraire la piste des dialogues."

            # 2. Application du style graphique personnalisé
            print(f"   -> Étape 2/3 : Application de la configuration (Taille: {TAILLE_POLICE})...")
            subs = SSAFile.load(srt_temp)
            subs.styles.clear()
            
            style_tv = SSAStyle()
            style_tv.fontname = "Arial"
            style_tv.fontsize = TAILLE_POLICE              
            style_tv.primarycolor = Color(255, 255, 255, 0) 
            style_tv.outlinecolor = Color(0, 0, 0, 0)       
            style_tv.outline = TAILLE_CONTOUR               
            style_tv.shadow = TAILLE_OMBRE                 
            
            subs.styles["Default"] = style_tv
            
            subs.save(ass_automatique, encoding="utf-8-sig")
            subs.save(ass_lisible, encoding="utf-8-sig")
            subs.save(ass_temp, encoding="utf-8-sig") 
            
            print(f"   ✅ Créé (Externe) : {nom_fichier_auto}")
            print(f"   ✅ Créé (Externe) : {nom_fichier_lisible}")

            # 3. Réintégration propre et ultra-stable via mkvmerge (Zéro conflit de flux possible)
            print(f"   -> Étape 3/3 : Injection de la piste stylisée via mkvmerge...")
            commande = [
                chemin_mkvmerge, '-o', video_sortie,
                video_entree, 
                '--track-name', '0:Français (Lisible TV)',
                '--language', '0:fre',
                '--default-track-flag', '0:yes',
                ass_temp
            ]
            
            res_remux = subprocess.run(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # mkvmerge renvoie 0 (succès) ou 1 (succès avec avertissements mineurs de tags, ce qui est OK)
            if res_remux.returncode in (0, 1) and os.path.exists(video_sortie):
                print(f"   ✅ Créé (Vidéo MKV) : {nom_video_sortie}\n")
                return True, "Succès"
            else:
                return False, f"Échec mkvmerge : {res_remux.stderr}"

        except Exception as e:
            return False, f"Erreur : {str(e)}"


def traiter_dossier():
    root = tk.Tk()
    root.withdraw()

    if not verifier_ffmpeg():
        return

    chemin_mkvmerge = garantir_mkvmerge()
    if not chemin_mkvmerge:
        messagebox.showerror("Outil Manquant", "Le composant requis 'mkvmerge' n'a pas pu être configuré.")
        return

    print("📂 Ouverture de la fenêtre de sélection de dossier...")
    dossier_selectionne = filedialog.askdirectory(title="Sélectionnez le dossier contenant vos fichiers MKV")
    
    if not dossier_selectionne:
        print("❌ Sélection annulée.")
        return

    fichiers_mkv = [f for f in os.listdir(dossier_selectionne) if f.lower().endswith('.mkv') and not f.endswith('_sous_titres.mkv')]
    
    if not fichiers_mkv:
        print("⚠ Aucun fichier .mkv à traiter trouvé dans ce dossier.")
        return

    total_fichiers = len(fichiers_mkv)
    print(f"🎬 {total_fichiers} fichier(s) MKV détecté(s). Début du traitement complet...\n")
    print("=" * 60)

    reussis = 0

    for index, nom_fichier in enumerate(fichiers_mkv, 1):
        chemin_entree = os.path.join(dossier_selectionne, nom_fichier)
        print(f"[{index}/{total_fichiers}] Traitement de : {nom_fichier}")
        success, message = modifier_et_reintegrer_mkv(chemin_entree, dossier_selectionne, chemin_mkvmerge)
        
        if success:
            reussis += 1
        else:
            print(f"   ❌ Ignoré : {message}\n")

    print("=" * 60)
    print(f"📊 Résumé : {reussis}/{total_fichiers} fichier(s) traité(s) avec succès.\n")


if __name__ == "__main__":
    try:
        traiter_dossier()
    except KeyboardInterrupt:
        print("\nOpération interrompue.")
    finally:
        print("\n" + "=" * 50)
        input("Appuyez sur Entrée pour fermer cette fenêtre...")
