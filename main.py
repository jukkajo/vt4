from operator import itemgetter
from functools import wraps
from flask import Flask, flash, render_template, redirect, url_for, session, make_response, request, config, Response
from polyglot import PolyglotForm
from wtforms import StringField, validators, BooleanField, SubmitField, ValidationError, SelectField, PasswordField, HiddenField
#from wtforms.fields import DateTimeLocalField
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
import datetime as d
import google.cloud.datastore as datastore
import os
import json
import hashlib
import requests
from itertools import groupby
#groupby


app = Flask(__name__)
app.secret_key = '!secret'
app.config.from_object('config')

CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth = OAuth(app)
oauth.register(
    name='google',
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid email profile'
    }
)

s1, s2, s3, s4, s5, s6 = "s1.xhtml","s2.xhtml", "s3.xhtml", "s4.xhtml", "s5.xhtml", "s6.xhtml"
main = "main"
P, G = "POST", "GET"
mt = "application/xhtml+xml;charset=UTF-8"

"""
@app.route('/data')
def alusta():
"""
def varmenna_lupa(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not 'user' in session:
            #paluu sivulle jolla kirjaudutaan
            return redirect(url_for('main'))
        return f(*args, **kwargs)
    return decorated
    

def pyyda_sposti(tk):
    pyyda = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            params={'access_token': tk})
    
    return pyyda.json()


#suorittaa varsinaisen queryn
def suorita_query(kind, jarjestys_param):
    cli = datastore.Client()
    data_olio = cli.query(kind=kind)
    data_olio.order = [jarjestys_param]
    return data_olio.fetch()
    
def lisaa_listaan(data_olio,luku):
    paluu_lista= []
    tmp = 1
    for ind in data_olio:
        if luku == 1:
            ind["ind"] = tmp
            tmp += 1
        paluu_lista.append(ind)
    return paluu_lista
    
#haetaan dataa datastoren tkannasta ja rakennetaan sovelluksen pääsivu
@app.route("/kilpailut", methods=[P,G])
@varmenna_lupa
def kilpailut():

    kilpailut = suorita_query("kilpailut", "kisanimi")
    sarjat = suorita_query("sarjat", "sarjanimi")
    joukkueet = suorita_query("joukkueet", "nimi")
    #sitten kerätään listat tiedoista joita sivulle tulostellaan
    
    #Kilpailut listataan uusin kilpailu (alkuajan mukaan) ensimmäisenä ja vanhin viimeisenä. 
    #knimet = lisaa_listaan(kilpailut,0)
    snimet = lisaa_listaan(sarjat,1)
    knimet = lisaa_listaan(kilpailut,0)
    knimet.sort(key=lambda item:item["alkuaika"], reverse=True)
    joukkueet_lista = sorted(list(lisaa_listaan(joukkueet,0)), key=lambda d: d["nimi"].lower())
    vastuu_henk = session.get("email_info")
    """
    sailo = []
    for i in range(len(knimet)):
       sailo.append(["",0])
    
    for i in range(len(knimet)):
        sailo[i][0] = knimet[i]
        sailo[i][1] = i
    session['sailo'] = sailo
    """
    return Response(render_template(s2, vastuu_henk=vastuu_henk, knimet=knimet, snimet=snimet, joukkueet=joukkueet_lista), mimetype=mt)

@app.route("/auth")
def auth():
    tk = oauth.google.authorize_access_token()
    u = tk.get("access_token")
    sposti = pyyda_sposti(u)
    session["email_info"] = sposti["email"]
    if u:
        session["user"] = u
    else:
        redirect("/")
    return redirect("/kilpailut")

#ohjataan googlen-tunnistautumiseen
@app.route("/login")
def login():
    redirect_uri = url_for("auth", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

#session tyhjennys ja ohjaus aloitussivulle  
@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')

#kun käyttäjä valitsee päsivun menusta kilpailun, tullaan tänne
@app.route("/kilpailut/<kilpailu>", methods=[P,G])
@varmenna_lupa
def kilpailu(kilpailu):
    #knimi_2019
    t = kilpailu.split('_')
    vuosi = t[1]
    v_kilpailu = t[0] 
    
    cli = datastore.Client()
    tmp = cli.query(kind="kilpailut").add_filter("kisanimi", "=", v_kilpailu).fetch()
    d = []
    for ind in tmp:
        d.append(ind)


    sarjat = cli.query(kind="sarjat")
    sarjat.order = ['sarjanimi']
    sarjat = sarjat.fetch()
    nimet = []
    
    for ind in sarjat:
        for ind2 in d:
        
            if ind["kilpailu"] == ind2["id"] and ind2["alkuaika"].year == int(vuosi):
                nimet.append(ind["sarjanimi"])
    
    #return Response(render_template(s3, nimet=nimet, kilpailu=kilpailu, tmp=tmp), mimetype=mt)
    return Response(render_template(s3, kilpailu=v_kilpailu, nimet=nimet, s=sarjat, vuosi=vuosi), mimetype=mt)

#tarkastaa lomakkeen jäsen-kenttiin syötetyn m-jono pituuden
def ptarkistin(form, field):
    if len(field.data.strip()) < 2:
        raise ValidationError("Nimen oltava väh. 2-merkkiä pitkä")

# tarkastaa, onko identtisiä jäseniä, ei ole case sensitiivinen         
def vertaile(lista, tunniste, sarja, joukkue, kilpailu):
    if tunniste == 0:
        for ind in lista:
            ind = ind.strip().upper()
        #============================
        sett = set()
        for ind in lista:
            if ind in sett:
                return True
            else:
                sett.add(ind)
             
    return False
        
#tämä tarkastaa, onko samoja joukkueita samassa kilpailussa
def j_dupl():
    cli = datastore.Client()
    query = cli.query(kind="joukkueet").fetch()
    i = 1
        
    sailo = []  
    for ind in query:
        sailo.append(ind)
            
    dupl = {1: {"joukkue":"", "sarja": 0}}
    #mahd duplikaattien dictionaryn koko myös mah. kasvussa, joten ei iteroida sitä vielä
    i=1
    for ind in sailo:
        dupl[i] = {"joukkue":ind["nimi"].strip().lower(), "sarja": ind["sarja"]}
        i += 1
            
    lista = [v for v in dupl.values()]
    #katsotaan, josko tietokannasta löytyisi duplikaatteja, ei siis kuuluisi siellä
    avain = "joukkue", "sarja"
    jarj_lista = lambda o: tuple(o[k] for k in avain)
    jarj = lambda o: tuple(o[k] for k in avain)
    u_lista = [{**dict(zip(avain, k)), "lkm": len([*l])} for k, l in groupby(sorted(lista, key=jarj_lista), jarj)]
        
    duplikaatti = False
    for i in range(len(u_lista)):
        if u_lista[i]["lkm"] > 1:
            duplikaatti = True

    return duplikaatti
    
#kun käyttäjä valitsee kilpailun menusta sarjan, tullaan tänne
@app.route('/kilpailut/<kilpailu>/<sarja>', methods=[P,G])
@varmenna_lupa
def sarja(kilpailu, sarja):

    t = kilpailu.split('_')
    vuosi = t[1]
    v_kilpailu = t[0]
    lisays_status=""
    k = []
    sarj_sailo = []
    i=0
    o=0
    p=None
    k_id = None
     
    esiintymat = sarja.count(' ')
    viestic = ""
    viestic1 = "Samannimiä jäseniä ei sallita, huomioi myös, ettei isot alkukirjaimet vaikuta."
    viestic2 = "Samanniminen joukkue jo ilmoitettu, keksi toinen nimi joukkueellesi."
    viestic3 = "Jokin meni pieleen, joukkueesi ei tallentunut :("
    
    class joukkue(PolyglotForm):
        nimi = StringField("Joukkueen nimi",validators=[ptarkistin])
        j1 = StringField("Jäsen 1", validators=[ptarkistin])
        j2 = StringField("Jäsen 2", validators=[ptarkistin])
        j3 = StringField("Jäsen 3")
        j4 = StringField("Jäsen 4")
        j5 = StringField("Jäsen 5")
    form = joukkue()

    #jos käyttäjä lähettää ja lomake hyväksyy, koitetaan tallentaa googlen päähän
    if request.method == P and form.validate():
        
        nimi = request.form.get("nimi")
        j1 = request.form.get("j1")
        j2 = request.form.get("j2")
        j3 = request.form.get("j3")
        j4 = request.form.get("j4")
        j5 = request.form.get("j5")
        
        sailo = []
        tmp = [j1,j2,j3,j4,j5]
        for ind in tmp:
            s = ind.strip()
            if s != "":
                sailo.append(ind)
                
        #duplikaattien vertailu jäsenistä, käyttää parametreistä sailoa ja numeroa
        vertailu = vertaile(sailo, 0, sarja, nimi, kilpailu)
        
        if vertailu == True:
            return render_template(s4, form=form, viestic=viestic1, sarja=sarja, esiintymat=esiintymat, v_kilpailu=v_kilpailu, vuosi=vuosi, n=neekeri, mimetype=mt)
        
        else:
         
            #jos jäsenet valideja yritetään lisätä joukkue, myöhemmin poistetaan, jos joukkueihin ilmestyy kaksi samaa
            cli = datastore.Client()
            sarjat = cli.query(kind="sarjat").fetch()
            #sarjat.order = ["sarjanimi"]
            kilpa = cli.query(kind="kilpailut").add_filter("kisanimi", "=", v_kilpailu).fetch()
        
            for ind in kilpa:
                k.append(ind)
        
            k_id = 0
        
            if k != []:
                for ind in k:
                    t_mp = str(ind["loppuaika"])
                    if t_mp[:4] == vuosi:
                        k_id = ind["id"]

            for ind in sarjat:
                sarj_sailo.append(ind)
        
            s = 1
            for i in range(len(sarj_sailo)):
                if sarj_sailo[i]["kilpailu"] == k_id:
                    if sarja == sarj_sailo[i]["sarjanimi"]:
                        s = i
                
        
            jasenet = list(filter(None, tmp))
            jasenet.sort()
        
            try:
                j = {"sarja": s, "nimi": nimi, "jasenet": jasenet, "kilpailu": k_id, "vastuu_henk":session.get('email_info')}
                cl = datastore.Client()
                tunniste_tmp = str(d.datetime.now())
                v_avain = cl.key("joukkueet", tunniste_tmp)
                v_entiteetti = datastore.Entity(key=v_avain)
                v_entiteetti.update({"avain": v_avain})
                #
                v_entiteetti.update({"kilpailu": k_id}) 
                #
                v_entiteetti.update(j)
                cl.put(v_entiteetti)
                #return render_template(s4,form=form,viestic=viestic3, mimetype=mt)
                lisays_status="Joukkueesi lisätty kilpailuun!"
            except:
                viestic=viestic3
            
            #lisätään ja etsitään jos duplikaatteja, jos ei, niin ei poistoa     
                    
            duplikaatti = j_dupl()
            if duplikaatti == True:
                #poisto tkannasta
                cli = datastore.Client()
                tmp = cli.query(kind="joukkueet").add_filter("nimi", "=", nimi).fetch()
                jlista = []
                for ind in tmp:
                    jlista.append(ind)
                joukkueDat = None
                if jlista[0]:
                    joukkueDat = jlista[0]
            
                cli = datastore.Client()
                cli.delete(joukkueDat["avain"])
                #palautetaan virheilmoitus,
                return render_template(s4, form=form, viestic=viestic2, sarja=sarja, esiintymat=esiintymat, v_kilpailu=v_kilpailu, vuosi=vuosi, mimetype=mt)
            
    return Response(render_template(s4, form=form, sarja=sarja, esiintymat=esiintymat, v_kilpailu=v_kilpailu, viestic=viestic, vuosi=vuosi, lisays_status=lisays_status), mimetype=mt)

#tällä luodaan entiteeteistä hierarkisia rakenteita
def luo_entityt(data_olio, cli, mjono):
    #tyyppi = "kilpailu"
    tunniste = 0

    for ind in data_olio:
    	#tässä vertailussa mjonot, aina vakiot, joten olkoon case-sensitiivinen
    	if mjono == "kilpailut" or mjono == "sarjat":
    	    tunniste += 1
    	    v_avain = cli.key(mjono, tunniste)
    	    v_entiteetti = datastore.Entity(key=v_avain)
    	else:
    	    #laitetaan avaimeksi vaikka aikaleima, kun ei niin väliä
    	    tunniste_tmp = str(d.datetime.now())
    	    v_avain = cli.key(mjono, tunniste_tmp)
    	    v_entiteetti = datastore.Entity(key=v_avain)
    	    v_entiteetti.update({"avain": v_avain})
    	    
    	v_entiteetti.update(ind)
    	cli.put(v_entiteetti)

#jos käyttäjä painaa lisäämänsä joukkueen linkkiä, ohjataan hänet tälle muokkaussivulle	
@app.route('/muokkaus_<nimi>', methods=[P,G])
@varmenna_lupa
def muokkaus(nimi):
    viesti = ""
    muokkaus_status=""
    cli = datastore.Client()
    tmp = cli.query(kind="joukkueet").add_filter("nimi", "=", nimi).fetch()
    jlista = []
    for ind in tmp:
        jlista.append(ind)
    joukkueDat = None
    if jlista[0]:
        joukkueDat = jlista[0]
        
    #h = str(joukkueDat["avain"])
    sarjat = cli.query(kind="sarjat")
    #sarjat.order = ["sarjanimi"]
    sarjat = sarjat.fetch()
    valinnat = []
    for ind in sarjat:
        if joukkueDat is not None:
            if ind["kilpailu"] == joukkueDat["kilpailu"]:
                valinnat.append(ind["sarjanimi"])
    #joukkueluokka lomakkeelle     
    class joukkue(PolyglotForm):
        poista = BooleanField("Poista joukkueesi")
        s_valinta = SelectField("Sarja", choices=valinnat)
        nimi = StringField("Joukkueen nimi",validators=[ptarkistin], default=joukkueDat["nimi"])
        j1 = StringField("Jäsen 1", validators=[ptarkistin], default=joukkueDat["jasenet"][0])
        j2 = StringField("Jäsen 2", validators=[ptarkistin], default=joukkueDat["jasenet"][1])
        #kokeillaan täyttää jäseniä, niissä kun vaihtoehtoisuutta
        try:
            j3 = StringField("Jäsen 3", default=joukkueDat['jasenet'][2])
        except:
            j3 = StringField("Jäsen 3")
        try:
            j4 = StringField("Jäsen 4", default=joukkueDat['jasenet'][3])
        except:
            j4 = StringField("Jäsen 4")
        try:
            j5 = StringField("Jäsen 5", default=joukkueDat['jasenet'][4])
        except:
            j5 = StringField("Jäsen 5")
            
    form = joukkue()
    
    #validointi, koska voihan olla, että vastuuhenkilö muuttanut joukkuetta hassusti
    #if request.method == P and form.validate():
    #edit tehdäänpäs validonti vasta myöhemmin
    if request.method == P:
        nimi = request.form.get("nimi")
        s_valinta = request.form.get("s_valinta")
        j1 = request.form.get("j1")
        j2 = request.form.get("j2")
        j3 = request.form.get("j3")
        j4 = request.form.get("j4")
        j5 = request.form.get("j5")
        poista_tf = request.form.get("poista")

        sailo2 = [j1,j2,j3,j4,j5]
        jasenet = []
        for ind in sailo2:
            if ind.strip() != "":
                jasenet.append(ind)

        vertailtavat = jasenet

        #jos raksi poistossa, niin koitetaan poistaa datastoresta
        if poista_tf == "y":
            try:
                cli = datastore.Client()
                #avain = cli.key("joukkueet", joukkueDat["avain"])
                cli.delete(joukkueDat["avain"])
                return redirect("/kilpailut")
            except:
                #leikitään että olisi hienot ja toimivat sivut
                viesti = "Joukkueen poistossa ilmeni ongelma, ota yhteyttä ylläpitoon"
        
        #jälleen, onko jäsenissä samannimisiä, true tai false
        jas_dupl = vertaile(vertailtavat, 0, "", "", "")
        
        if jas_dupl == True:
            viesti = "Samannimiset jäsenevät eivät ole sallittuja"
            return render_template(s5,form=form,viesti=viesti, viesti2=viesti2, nimi=nimi, mimetype=mt)
        
        #==============================================================================================
        cli = datastore.Client()
        avain = cli.key("joukkueet", joukkueDat["avain"])
        paivitetty = datastore.Entity(avain)
        #{"sarja": sarjat, "nimi": nimi, "jasenet": jasenet, "vastuu_henk":session.get('email_info')}
        sarja=1
        i = 0
        for ind in valinnat:
            #if s_valinta == ind["sarjanimi"]:
            if s_valinta == ind:
                break  
            sarja += 1
            i += 1
            
        #paivitetty.update({"nimi":nimi, "jasenet":sailo2, "kilpailu":joukkueDat["kilpailu"], "sarja":sarja, "vastuu_henk":joukkueDat["vastuu_henk"], "avain":av_t[19:45]})
        paivitetty.update({"nimi":nimi, "jasenet":sailo2, "kilpailu":joukkueDat["kilpailu"], "sarja":sarja, "vastuu_henk":joukkueDat["vastuu_henk"]})
        cli.put(paivitetty)
        
        #onko duplikaatteja joukkueissa
        j_dupl  = j_dupl()   
        if j_dupl == True:
            #poistetaan lisätty joukkue ja palautetaan v-ilmoitus
            cli = datastore.Client()
            avain = cli.key("joukkueet", joukkueDat["avain"])
            cli.delete(avain)
            viesti = "Joukkue jo kilpailussa, anna joukkueellesi toinen nimi"
            return render_template(s5, form=form, viesti=viesti, nimi=nimi, mimetype=mt)

        else:
            muokkaus_status="Muutokset tallennettu!"
            #==============================================================================================
    #return render_template(s6, jlista=jlista, joukkueDat=joukkueDat, muokkaus_status=muokkaus_status, sarja=sarja, h=h, mimetype=mt)
    return render_template(s5, jlista=jlista, tmp=tmp, joukkue=joukkueDat, form=form, nimi=nimi, muokkaus_status=muokkaus_status, mimetype=mt)
	
@app.route('/')
def main():
    #loin tällä entiteetit, loisi jatkuvasti lisää, aina kun kirjautumissivun resursseja pyydettäisiin, jätetään nyt tänne kuitenkin
    """
    kilpailut = [{"id": 1, "kisanimi":"Jäärogaining", "loppuaika": "2019-03-17 20:00:00", "alkuaika": "2019-03-15 09:00:00"},
    		 {"id": 2, "kisanimi":"Fillarirogaining", "loppuaika": "2016-03-17 20:00:00", "alkuaika": "2016-03-15 09:00:00"},
    		 {"id": 3, "kisanimi":"Kintturogaining", "loppuaika": "2017-03-18 20:00:00", "alkuaika": "2017-03-18 09:00:00"},
    		 {"id": 99, "kisanimi":"Jäärogaining", "loppuaika": "2021-05-01 20:00:00", "alkuaika": "2021-05-01 12:00:00"}]
    for dic_t in kilpailut: 
    	dic_t["loppuaika"] = d.datetime.strptime(dic_t["loppuaika"], "%Y-%m-%d %H:%M:%S")
    	dic_t["alkuaika"] = d.datetime.strptime(dic_t["alkuaika"], "%Y-%m-%d %H:%M:%S")

    sarjat = [{"sarjanimi":"4 h", "kilpailu": 1, "kesto": 4},
    	      {"sarjanimi":"2 h", "kilpailu": 1, "kesto": 2},
    	      {"sarjanimi":"8 h", "kilpailu": 1, "kesto": 8},
    	      {"sarjanimi":"Pikkusarja", "kilpailu": 3, "kesto": 4},
    	      {"sarjanimi":"8 h", "kilpailu": 3, "kesto": 8},
    	      {"sarjanimi":"Isosarja", "kilpailu": 3, "kesto": 8},
    	      {"sarjanimi":"Pääsarja", "kilpailu": 2, "kesto": 4},
    	      {"sarjanimi":"2 h", "kilpailu": 2, "kesto": 2}]
    	      
    joukkueet = [{"sarja": 3, "nimi": "Onnenonkijat", "jasenet": ["Antero Paununen", "Pekka Paununen", "Raimo Laine"]},
     		{"sarja": 3, "nimi": "Mudan Ystävät", "jasenet": ["Kaija Kinnunen", "Teija Kinnunen"]},
     		{"sarja": 3, "nimi": "Vara 3", "jasenet": ["barbar", "foofoo"]},
     		{"sarja": 3, "nimi": "Tollot", "jasenet": ["Juju", "Tappi"]},
     		{"sarja": 3, "nimi": "Kahden joukkue", "jasenet": ["Matti Humppa", "Miikka Talvinen"]},
     		{"sarja": 3, "nimi": "Siskokset", "jasenet": ["Sanna Haavikko", "Seija Kallio"]},
     		{"sarja": 3, "nimi": "Dynamic Duo", "jasenet": ["Karhusolan Rentukka", "Kutajoen Tiukunen"]}, 
     		{"sarja": 3, "nimi": "Toipilas", "jasenet": ["Leena Annila", "Satu Lehtonen"]},
     		{"sarja": 3, "nimi": "Sopupeli", "jasenet": ["Antti Haukio", "Janne Hautanen", "Taina Pekkanen", "Venla Kujala"]},
     		{"sarja": 1, "nimi": "Retkellä v 13", "jasenet": ["Henna Venäläinen", "Katja Vitikka"]},
     		{"sarja": 1, "nimi": "Pelättimet", "jasenet": ["Kari Vaara", "Katja Vaara"]},
     		{"sarja": 3, "nimi": "Kaakelin putsaajat", "jasenet": ["Jaana Kaajanen", "Mikko Kaajanen", "Timo Ruonanen"]},
     		{"sarja": 3, "nimi": "Vara 1", "jasenet": ["barfoo","foobar"]},
     		{"sarja": 2, "nimi": "Hullut fillaristit", "jasenet": ["Hannele Saari", "Paula Kujala"]},
     		{"sarja": 2, "nimi": "Kotilot", "jasenet": ["Jaana Meikäläinen", "Kaisa Konttinen", "Maija Meikäläinen", "Niina Salonen"]},
     		{"sarja": 3, "nimi": "Rennot 1", "jasenet": ["Anja Huttunen", "Siru Kananen"]},
     		{"sarja": 3, "nimi": "Vara 2", "jasenet": ["bar","foo"]},
     		{"sarja": 1, "nimi": "Vapaat", "jasenet": ["Juha Vapaa", "Matti Vapaa"]},
     		{"sarja": 3, "nimi": "Susi jo syntyessään", "jasenet": ["Janne Pannunen", "Riku Aarnio"]},
     		{"sarja": 3, "nimi": "Vara 4", "jasenet": ["foo","bar"]},
     		{"sarja": 1, "nimi": "Rennot 2", "jasenet": ["Heikki Häkkinen", "Piia Virtanen", "Sari Maaninka"]},
     		{"sarja": 1, "nimi": "Tähdenlento", "jasenet": ["Anu", "Virva"]},
     		{"sarja": 3, "nimi": "RogRog", "jasenet": ["Antti Kaakkuri", "Mikko Meikäläinen", "Pekka Kosonen", "Samuli Paavola"]},
     		{"sarja": 5, "nimi": "Onnenonkijat", "jasenet": ["Antero Paununen", "Pekka Paununen", "Raimo Laine"]},
     		{"sarja": 5, "nimi": "Mudan Ystävät", "jasenet": ["Kaija Kinnunen", "Teija Kinnunen"]},
     		{"sarja": 5, "nimi": "Vara 3", "jasenet": ["barbar", "foofoo"]},
     		{"sarja": 6, "nimi": "Tollot", "jasenet": ["Juju", "Tappi"]},
     		{"sarja": 6, "nimi": "Kahden joukkue", "jasenet": ["Matti Humppa", "Miikka Talvinen"]},
     		{"sarja": 8, "nimi": "Siskokset", "jasenet": ["Sanna Haavikko", "Seija Kallio"]}]

    cli = datastore.Client()
    #kokeillaan, josko käyttäjä olisi jo istunnossa
    
    luo_entityt(kilpailut, cli, "kilpailut")
    luo_entityt(sarjat, cli, "sarjat")
    luo_entityt(joukkueet, cli, "joukkueet")
    """
    k = session.get('user')
    return render_template(s1, k=k, mimetype=mt)

    

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
