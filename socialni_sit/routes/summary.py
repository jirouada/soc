from flask import Blueprint, request, redirect, url_for, render_template, session, flash, jsonify
from db.neo4j_connection import Neo4jConnection

auth_blueprint = Blueprint('auth', __name__)
profile_blueprint = Blueprint('profile', __name__)
challenges_blueprint = Blueprint('challenges', __name__)

# 1. CREATE - Registrace nového uživatele
@auth_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    """
    - Uživatel vyplní formulář z template (jméno, věk, heslo, zájmy) a tyto údaje se odešlou přes POST.
    - Kód v podmínce "POST" vezme data z formuláře, vytvoří nový záznam v databázi a uloží je jako nový uzel `User`.
    - Po registraci je uživatel přesměrován na přihlašovací stránku (v rámci tohoto souboru není uveden daný route (případně v auth.py)).
    """
    if request.method == 'POST':  # Zpracování odeslaného formuláře
        username = request.form['username']  # Načítá poskytnuté informace z formulářů
        age = request.form['age']
        password = request.form['password']
        interests = request.form['interests'].split(',')  # Rozdělení zájmů na seznam

        conn = Neo4jConnection()  # Připojení k databázi
        conn.query(
            "CREATE (u:User {username: $username, age: $age, password: $password, interests: $interests})",
            {'username': username, 'age': int(age), 'password': password, 'interests': interests}
        ) #Dotaz cypher na databázi, vytváří nový uzel "User" pomocí poskytnutých proměnných
        conn.close()  # Uzavření připojení
        flash("Registrace proběhla úspěšně!", "success")
        return redirect(url_for('auth.login'))  # Přesměrování na přihlašovací stránku

    return render_template('register.html')  # Načtení stránky formuláře pro registraci

# 2. READ - Zobrazení profilu uživatele
@profile_blueprint.route('/profile')
def view_profile():
    """
    - Načítá údaje o aktuálně přihlášeném uživateli (jméno, body, role, vytvořené a dokončené výzvy).
    - Data se berou ze session (kdo je přihlášený) a pak se dotazují v databázi Neo4j.
    - Vše se kontextuálně zobrazí na stránce profilu.
    """
    if 'username' not in session:  # Pokud uživatel není přihlášený, je přesměrován na login
        return redirect(url_for('auth.login'))  

    username = session['username']  # Uživatelské jméno přihlášeného uživatele
    conn = Neo4jConnection()

    # Načítá body a roli uživatele z databáze
    user_data = conn.query(
        "MATCH (u:User {username: $username}) RETURN u.points AS points, u.role AS role",
        {'username': username} #Zde dostávám seznam slovníků, kdy každý slovník představuje jeden nalezený uzel
    )
    points = user_data[0]['points'] if user_data else 0  # Body (výchozí 0), specifikuju user_data[0] protože chci jen data prvního uživatele ze seznamu
    role = user_data[0]['role'] if user_data else "user"  # Role (výchozí "user") specifikuju user_data[0] protože chci jen data prvního uživatele ze seznamu

    # Načítá výzvy vytvořené uživatelem
    created_challenges = conn.query(
        "MATCH (u:User {username: $username})-[:CREATED]->(c:Challenge) RETURN c.id AS id, c.name AS name",
        {'username': username}
    )

    # Načítá výzvy dokončené uživatelem
    completed_challenges = conn.query(
        "MATCH (u:User {username: $username})-[rel:COMPLETED]->(c:Challenge) RETURN c.id AS id, c.name AS name, rel.result AS result",
        {'username': username}
    )
    conn.close()

    # Zobrazení dat (kontext) na stránce profilu
    return render_template(
        'profile.html',
        user={'username': username, 'points': points, 'role': role},
        created_challenges=created_challenges,
        completed_challenges=completed_challenges
    )

# 3. UPDATE - Úprava profilu uživatele
@profile_blueprint.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    """
    - Načítá aktuální údaje o uživateli a umožňuje je změnit (jméno, věk, zájmy).
    - Data z formuláře se po odeslání uloží do databáze.
    - Po úpravě se přesměruje zpět na profil.
    """
    if 'username' not in session:  # Pokud uživatel není přihlášený, je přesměrován na login
        return redirect(url_for('auth.login'))

    username = session['username'] #přebíra username ze session
    conn = Neo4jConnection()

    if request.method == 'POST':  # Zpracování dat z edit formuláře
        new_username = request.form['username']
        new_age = request.form['age']
        new_interests = request.form['interests'].split(',')

        # Aktualizace uživatelských údajů v databázi
        conn.query(
            "MATCH (u:User {username: $username}) "
            "SET u.username = $new_username, u.age = $new_age, u.interests = $new_interests",
            {'username': username, 'new_username': new_username, 'new_age': int(new_age), 'new_interests': new_interests}
        )
        session['username'] = new_username  # Aktualizace uživatelského jména v session
        conn.close()
        flash("Údaje byly úspěšně aktualizovány!", "success") #Na další stránce upozornění
        return redirect(url_for('profile.view_profile'))  # Přesměrování na profil

    # Načítání aktuálních údajů pro zobrazení ve formuláři
    user = conn.query("MATCH (u:User {username: $username}) RETURN u", {'username': username})
    conn.close()
    return render_template('edit_profile.html', user=user[0]['u']) #Načte stránku s formulářem na update v kontextu s vyhledaným uzlem.

# 4. DELETE - Smazání výzvy
@challenges_blueprint.route('/delete_challenge/<challenge_id>', methods=['POST'])
def delete_challenge(challenge_id):
    """
    - Na základě ID výzvy smaže danou výzvu z databáze.
    - Pokud operace proběhne úspěšně, vrátí informaci o úspěchu.
    """
    if 'username' not in session:  # Pokud uživatel není přihlášený, je přesměrován na login
        return jsonify({'success': False, 'error': 'User not authenticated'}), 401 # Vrací JSON s chybou a HTTP kódem 401, pokud uživatel není přihlášen.

    conn = Neo4jConnection()

    try:
        # Smazání výzvy podle ID
        conn.query("MATCH (c:Challenge {id: $id}) DETACH DELETE c", {'id': challenge_id}) #Hledá challenge pomocí ID, pokud nalezne maže
        conn.close()
        flash("Výzva byla úspěšně smazána.", "success")
        return jsonify({'success': True}), 200 # Vrací JSON s potvrzením úspěchu a HTTP kódem 200, pokud akce proběhla správně.
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500 # Vrací JSON s chybou a HTTP kódem 500, pokud na serveru došlo k chybě.







