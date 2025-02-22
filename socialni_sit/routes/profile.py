from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from db.neo4j_connection import Neo4jConnection

profile_blueprint = Blueprint('profile', __name__)

@profile_blueprint.route('/profile')
def view_profile():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    conn = Neo4jConnection()

    # Načíst uživatelské údaje
    user_data = conn.query(
        "MATCH (u:User {username: $username}) RETURN u", 
        {'username': session['username']}
    )
    if not user_data:
        flash("Uživatel nebyl nalezen.", "danger")
        return redirect(url_for('auth.login'))
    
    user = user_data[0]['u']

    # Načíst výzvy, které uživatel vytvořil, k nimž se přihlásil nebo je dokončil
    created_challenges = conn.query(
        """
        MATCH (u:User {username: $username})-[:CREATED]->(c:Challenge)
        RETURN c
        """,
        {'username': session['username']}
    )
    
    joined_challenges = conn.query(
        """
        MATCH (u:User {username: $username})-[:JOINED]->(c:Challenge)
        RETURN c
        """,
        {'username': session['username']}
    )
    
    completed_challenges = conn.query(
        """
        MATCH (u:User {username: $username})-[:COMPLETED]->(c:Challenge)
        RETURN c
        """,
        {'username': session['username']}
    )

    # Načíst body uživatele
    points = user.get('points', 0)

    conn.close()

    return render_template(
        'profile.html',
        user=user,
        created_challenges=created_challenges,
        joined_challenges=joined_challenges,
        completed_challenges=completed_challenges,
        points=points
    )

@profile_blueprint.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    username = session['username']
    conn = Neo4jConnection()

    if request.method == 'POST':
        new_username = request.form['username']
        new_age = request.form['age']
        new_interests = request.form['interests'].split(',')

        conn.query("MATCH (u:User {username: $username}) "
                   "SET u.username = $new_username, u.age = $new_age, u.interests = $new_interests",
                   {'username': username, 'new_username': new_username, 'new_age': int(new_age), 'new_interests': new_interests})
        
        session['username'] = new_username
        conn.close()
        return redirect(url_for('profile.view_profile'))

    user = conn.query("MATCH (u:User {username: $username}) RETURN u", {'username': username})
    conn.close()
    return render_template('edit_profile.html', user=user[0]['u'])

@profile_blueprint.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('auth.login'))


@profile_blueprint.route('/user/<username>')
def view_other_profile(username):
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    conn = Neo4jConnection()

    # Výzvy, které uživatel vytvořil
    created_challenges = conn.query(
        """
        MATCH (u:User {username: $username})-[:CREATED]->(c:Challenge)
        RETURN c.id AS id, c.name AS name, c.hashtags AS hashtags
        """,
        {'username': username}
    )

    # Splněné výzvy
    completed_challenges = conn.query(
        "MATCH (u:User {username: $username})-[:COMPLETED]->(c:Challenge) RETURN c",
        {'username': username}
    )

    conn.close()
    return render_template(
        'profile.html', 
        user={'username': username},
        created_challenges=created_challenges,
        completed_challenges=completed_challenges,
        is_self=False  # Označení, že jde o jiný profil
    )