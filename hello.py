import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask import Flask, render_template, session, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# --- Configurações ---
app.config['SECRET_KEY'] = 'uma string bem dificil de adivinhar'

# Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] =\
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Variáveis de Ambiente para o SendGrid e Aluno
app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY')
app.config['API_FROM'] = os.environ.get('API_FROM')
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')
app.config['STUDENT_ID'] = os.environ.get('STUDENT_ID')
app.config['STUDENT_NAME'] = os.environ.get('STUDENT_NAME')

# Inicialização das Extensões
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Modelos do Banco de Dados ---
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = ['User', 'Administrator']
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
                db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    def __repr__(self):
        return '<User %r>' % self.username

# --- Formulário ---
class NameForm(FlaskForm):
    name = StringField('Qual é o seu nome?', validators=[DataRequired()])
    send_email = BooleanField('Deseja enviar e-mail para flaskaulasweb@zohomail.com?')
    submit = SubmitField('Submit')

# --- Função de Envio de E-mail (com SendGrid) ---
def send_email_sendgrid(to, subject, new_user):
    """Envia um e-mail usando a API do SendGrid."""
    message = Mail(
        from_email=app.config['API_FROM'],
        to_emails=to,
        subject=subject,
        html_content=f"""
            <h3>Novo Usuário Cadastrado!</h3>
            <p><strong>Prontuário do Aluno:</strong> {app.config['STUDENT_ID']}</p>
            <p><strong>Nome do Aluno:</strong> {app.config['STUDENT_NAME']}</p>
            <hr>
            <p><strong>Nome do novo usuário:</strong> {new_user}</p>
        """
    )
    try:
        sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])
        response = sg.send(message)
        print(f"E-mail enviado para {to}, status: {response.status_code}")
    except Exception as e:
        print(f"Erro ao enviar e-mail para {to}: {e}")

# --- Rotas da Aplicação ---
@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Role=Role)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/', methods=['GET', 'POST'])
def index():
    form = NameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()
        if user is None:
            # Define o papel do usuário (Administrator ou User)
            admin_role = Role.query.filter_by(name='Administrator').first()
            user_role = Role.query.filter_by(name='User').first()
            # O primeiro usuário cadastrado (ou 'john') será o admin
            if User.query.count() == 0 or form.name.data.lower() == 'john':
                 new_user = User(username=form.name.data, role=admin_role)
            else:
                 new_user = User(username=form.name.data, role=user_role)
            
            db.session.add(new_user)
            db.session.commit()
            session['known'] = False
            flash('E-mail(s) enviado(s) com sucesso!')

            # Envia e-mail para o administrador 
            if app.config['FLASKY_ADMIN']:
                send_email_sendgrid(
                    to=app.config['FLASKY_ADMIN'],
                    subject='[Receba Jr] Novo Usuário',
                    new_user=form.name.data
                )
            
            # Se a caixa de seleção foi marcada, envia para o e-mail adicional
            if form.send_email.data:
                send_email_sendgrid(
                    to='flaskaulasweb@zohomail.com',
                    subject='[Receba Jr] Novo Usuário',
                    new_user=form.name.data
                )
        else:
            session['known'] = True
        
        session['name'] = form.name.data
        form.name.data = ''
        return redirect(url_for('index'))

    # Busca todos os usuários para exibir na tabela
    users = User.query.order_by(User.id.asc()).all()
    
    return render_template('index.html', form=form, name=session.get('name'),
                           known=session.get('known', False), users=users)
