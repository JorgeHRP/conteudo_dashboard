from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
import auth
import config
from data.loader import start_loader, aplicar_filtros, get_cursos, get_ies, get_evolucao, uniq as _uniq

def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.permanent_session_lifetime = timedelta(hours=8)

    # ─── HELPERS ─────────────────────────────────────────────

    def dash_ctx(modulo):
        user = auth.get_current_user()
        return {
            "current_user":    user,
            "allowed_modules": auth.get_allowed_modules(user["id"], user["role"]) if user else [],
            "active_module":   modulo,
        }

    def get_filters():
        """Lê todos os parâmetros de filtro da query string."""
        return {k: request.args.get(k) for k in [
            "regiao", "uf", "modalidade", "area", "rede",
            "grau", "org_academica", "microrregiao", "municipio",
            "co_ies", "no_ies", "sg_ies", "tipo_ies",
        ]}

    def kpi_data(params):
        df  = aplicar_filtros(get_cursos(), params)
        ies = aplicar_filtros(get_ies(),    params, prefixo="ies")
        vagas = int(df["QT_VG_TOTAL"].sum()) if "QT_VG_TOTAL" in df.columns else 0
        ing   = int(df["QT_ING"].sum())
        mat   = int(df["QT_MAT"].sum())
        conc  = int(df["QT_CONC"].sum())
        return {
            "total_matriculas":   mat,
            "total_ingressantes": ing,
            "total_concluintes":  conc,
            "total_vagas":        vagas,
            "total_cursos":       int(df["NO_CURSO"].nunique()) if "NO_CURSO" in df.columns else len(df),
            "total_ies":          len(ies),
            "taxa_ocupacao":      round(ing  / vagas * 100, 2) if vagas else 0,
            "taxa_permanencia":   round(mat  / ing   * 100, 2) if ing   else 0,
            "taxa_conclusao":     round(conc / mat   * 100, 2) if mat   else 0,
        }

    # ─── AUTH ────────────────────────────────────────────────

    @app.route("/")
    def index():
        if auth.get_current_user():
            return redirect(url_for("overview"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if auth.get_current_user():
            return redirect(url_for("overview"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = auth.authenticate(username, password)
            if user:
                auth.set_session(user)
                return redirect(url_for("overview"))
            error = "Usuário ou senha inválidos."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        auth.clear_session()
        return redirect(url_for("login"))

    # ─── OVERVIEW ────────────────────────────────────────────

    @app.route("/dashboard/overview")
    @auth.login_required
    @auth.module_required("overview")
    def overview():
        return render_template("dashboard/overview.html", **dash_ctx("overview"))

    @app.route("/api/kpis")
    @auth.login_required
    def api_kpis():
        return jsonify(kpi_data(get_filters()))

    @app.route("/api/filtros")
    @auth.login_required
    def api_filtros():
        cursos = get_cursos()
        ies    = get_ies()
        return jsonify({
            # Geográficos
            "regioes":       _uniq(cursos, "NO_REGIAO"),
            "ufs":           _uniq(cursos, "SG_UF"),
            "microrregioes": _uniq(cursos, "NO_MICRORREGIAO"),
            "municipios":    _uniq(cursos, "NO_MUNICIPIO"),
            # Curso
            "areas":         _uniq(cursos, "NO_CINE_AREA_GERAL"),
            "graus":         _uniq(cursos, "TP_GRAU_ACADEMICO"),
            # IES
            "redes":         _uniq(cursos, "TP_REDE_LABEL"),
            "org_academica": _uniq(ies,    "TP_ORGANIZACAO_ACADEMICA"),
            # IES lookup — lista de objetos {co, nome, sigla}
            "ies_lista": (
                ies[["CO_IES", "NO_IES", "SG_IES"]]
                .dropna(subset=["NO_IES"])
                .sort_values("NO_IES")
                .rename(columns={"CO_IES": "co", "NO_IES": "nome", "SG_IES": "sigla"})
                .to_dict(orient="records")
            ),
        })

    @app.route("/api/overview/regiao")
    @auth.login_required
    def api_overview_regiao():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_REGIAO")["QT_MAT"].sum().reset_index()
        r.columns = ["regiao", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).to_dict(orient="records"))

    @app.route("/api/overview/modalidade")
    @auth.login_required
    def api_overview_modalidade():
        df  = aplicar_filtros(get_cursos(), get_filters())
        MAP = {"1": "Presencial", "2": "EAD", "3": "Semi-presencial"}
        r   = df.groupby("TP_MODALIDADE_ENSINO")["QT_MAT"].sum().reset_index()
        r["TP_MODALIDADE_ENSINO"] = r["TP_MODALIDADE_ENSINO"].astype(str).map(MAP).fillna("Outro")
        r.columns = ["modalidade", "matriculas"]
        return jsonify(r.to_dict(orient="records"))

    @app.route("/api/overview/uf")
    @auth.login_required
    def api_overview_uf():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("SG_UF")["QT_MAT"].sum().reset_index()
        r.columns = ["uf", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).to_dict(orient="records"))

    @app.route("/api/overview/genero")
    @auth.login_required
    def api_overview_genero():
        df = aplicar_filtros(get_cursos(), get_filters())
        return jsonify([
            {"genero": "Feminino",  "valor": int(df["QT_MAT_FEM"].sum())},
            {"genero": "Masculino", "valor": int(df["QT_MAT_MASC"].sum())},
        ])

    # ─── MATRÍCULAS ──────────────────────────────────────────

    @app.route("/dashboard/matriculas")
    @auth.login_required
    @auth.module_required("matriculas")
    def matriculas():
        return render_template("dashboard/matriculas.html", **dash_ctx("matriculas"))

    @app.route("/api/matriculas/area")
    @auth.login_required
    def api_matriculas_area():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_CINE_AREA_GERAL")["QT_MAT"].sum().reset_index()
        r.columns = ["area", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).head(10).to_dict(orient="records"))

    @app.route("/api/matriculas/uf")
    @auth.login_required
    def api_matriculas_uf():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("SG_UF")["QT_MAT"].sum().reset_index()
        r.columns = ["uf", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).to_dict(orient="records"))

    @app.route("/api/matriculas/modalidade")
    @auth.login_required
    def api_matriculas_modalidade():
        """Distribuição Presencial / EAD / Semi — para donut."""
        df  = aplicar_filtros(get_cursos(), get_filters())
        MAP = {"1": "Presencial", "2": "EAD", "3": "Semi-presencial"}
        r   = df.groupby("TP_MODALIDADE_ENSINO")["QT_MAT"].sum().reset_index()
        r["modalidade"] = r["TP_MODALIDADE_ENSINO"].astype(str).map(MAP).fillna("Outro")
        r = r[["modalidade", "QT_MAT"]].rename(columns={"QT_MAT": "matriculas"})
        return jsonify(r.sort_values("matriculas", ascending=False).to_dict(orient="records"))

    @app.route("/api/matriculas/genero")
    @auth.login_required
    def api_matriculas_genero():
        """Split feminino / masculino — para donut."""
        df = aplicar_filtros(get_cursos(), get_filters())
        return jsonify([
            {"genero": "Feminino",  "valor": int(df["QT_MAT_FEM"].sum())},
            {"genero": "Masculino", "valor": int(df["QT_MAT_MASC"].sum())},
        ])

    @app.route("/api/matriculas/cursos_top")
    @auth.login_required
    def api_matriculas_cursos_top():
        """Ranking dos 15 cursos com mais matrículas."""
        df    = aplicar_filtros(get_cursos(), get_filters())
        r     = df.groupby("NO_CURSO")[["QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL"]].sum().reset_index()
        r     = r.sort_values("QT_MAT", ascending=False).head(15)
        total = r["QT_MAT"].sum() or 1
        r["market_share"] = (r["QT_MAT"] / total * 100).round(2)
        r["taxa_ocup"]    = (r["QT_ING"] / r["QT_VG_TOTAL"].replace(0, 1) * 100).round(1)
        return jsonify(r.rename(columns={
            "NO_CURSO":    "curso",
            "QT_MAT":      "matriculas",
            "QT_ING":      "ingressantes",
            "QT_CONC":     "concluintes",
            "QT_VG_TOTAL": "vagas",
        }).to_dict(orient="records"))

    @app.route("/api/matriculas/ies_top")
    @auth.login_required
    def api_matriculas_ies_top():
        """Top 15 IES por matrículas com market share."""
        df    = aplicar_filtros(get_cursos(), get_filters())
        ies_d = get_ies()[["CO_IES", "NO_IES", "SG_IES",
                            "SG_UF_IES", "TP_ORGANIZACAO_ACADEMICA"]].copy()
        ies_d["CO_IES"] = ies_d["CO_IES"].astype(str)

        r = (
            df.groupby("CO_IES")[["QT_MAT", "QT_ING", "QT_CONC"]]
            .sum().reset_index()
        )
        r = r.merge(ies_d, on="CO_IES", how="left")
        r = r.sort_values("QT_MAT", ascending=False).head(15)

        total = r["QT_MAT"].sum() or 1
        r["market_share"] = (r["QT_MAT"] / total * 100).round(2)

        return jsonify(r.rename(columns={
            "CO_IES":                 "co_ies",
            "NO_IES":                 "ies",
            "SG_IES":                 "sigla",
            "SG_UF_IES":              "uf",
            "TP_ORGANIZACAO_ACADEMICA":"org",
            "QT_MAT":                 "matriculas",
            "QT_ING":                 "ingressantes",
            "QT_CONC":                "concluintes",
        }).to_dict(orient="records"))

    @app.route("/api/matriculas/grau")
    @auth.login_required
    def api_matriculas_grau():
        """Distribuição por grau acadêmico (Bacharelado, Licenciatura, Tecnólogo…)."""
        df = aplicar_filtros(get_cursos(), get_filters())
        if "TP_GRAU_ACADEMICO" not in df.columns:
            return jsonify([])
        r = df.groupby("TP_GRAU_ACADEMICO")["QT_MAT"].sum().reset_index()
        r.columns = ["grau", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).to_dict(orient="records"))

    @app.route("/api/matriculas/rede")
    @auth.login_required
    def api_matriculas_rede():
        """Distribuição por rede (Federal, Estadual, Municipal, Privada)."""
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("TP_REDE_LABEL")["QT_MAT"].sum().reset_index()
        r.columns = ["rede", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).to_dict(orient="records"))

    # ─── INGRESSANTES ────────────────────────────────────────

    @app.route("/dashboard/ingressantes")
    @auth.login_required
    @auth.module_required("ingressantes")
    def ingressantes():
        return render_template("dashboard/ingressantes.html", **dash_ctx("ingressantes"))

    @app.route("/api/ingressantes/area")
    @auth.login_required
    def api_ingressantes_area():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_CINE_AREA_GERAL")["QT_ING"].sum().reset_index()
        r.columns = ["area", "ingressantes"]
        return jsonify(r.sort_values("ingressantes", ascending=False).head(10).to_dict(orient="records"))

    @app.route("/api/ingressantes/regiao")
    @auth.login_required
    def api_ingressantes_regiao():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_REGIAO")["QT_ING"].sum().reset_index()
        r.columns = ["regiao", "ingressantes"]
        return jsonify(r.sort_values("ingressantes", ascending=False).to_dict(orient="records"))

    @app.route("/api/ingressantes/uf")
    @auth.login_required
    def api_ingressantes_uf():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("SG_UF")["QT_ING"].sum().reset_index()
        r.columns = ["uf", "ingressantes"]
        return jsonify(r.sort_values("ingressantes", ascending=False).to_dict(orient="records"))

    @app.route("/api/ingressantes/modalidade")
    @auth.login_required
    def api_ingressantes_modalidade():
        df  = aplicar_filtros(get_cursos(), get_filters())
        MAP = {"1": "Presencial", "2": "EAD", "3": "Semi-presencial"}
        r   = df.groupby("TP_MODALIDADE_ENSINO")["QT_ING"].sum().reset_index()
        r["modalidade"] = r["TP_MODALIDADE_ENSINO"].astype(str).map(MAP).fillna("Outro")
        r = r[["modalidade", "QT_ING"]].rename(columns={"QT_ING": "ingressantes"})
        return jsonify(r.sort_values("ingressantes", ascending=False).to_dict(orient="records"))

    @app.route("/api/ingressantes/cursos_top")
    @auth.login_required
    def api_ingressantes_cursos_top():
        df    = aplicar_filtros(get_cursos(), get_filters())
        r     = df.groupby("NO_CURSO")[["QT_ING", "QT_MAT", "QT_VG_TOTAL"]].sum().reset_index()
        r     = r.sort_values("QT_ING", ascending=False).head(15)
        total = r["QT_ING"].sum() or 1
        r["market_share"] = (r["QT_ING"] / total * 100).round(2)
        return jsonify(r.rename(columns={
            "NO_CURSO": "curso", "QT_ING": "ingressantes",
            "QT_MAT": "matriculas", "QT_VG_TOTAL": "vagas",
        }).to_dict(orient="records"))

    @app.route("/api/ingressantes/ies_top")
    @auth.login_required
    def api_ingressantes_ies_top():
        df    = aplicar_filtros(get_cursos(), get_filters())
        ies_d = get_ies()[["CO_IES", "NO_IES", "SG_IES", "SG_UF_IES"]].copy()
        ies_d["CO_IES"] = ies_d["CO_IES"].astype(str)
        r = df.groupby("CO_IES")[["QT_ING", "QT_MAT"]].sum().reset_index()
        r = r.merge(ies_d, on="CO_IES", how="left").sort_values("QT_ING", ascending=False).head(15)
        total = r["QT_ING"].sum() or 1
        r["market_share"] = (r["QT_ING"] / total * 100).round(2)
        return jsonify(r.rename(columns={
            "CO_IES": "co_ies", "NO_IES": "ies", "SG_IES": "sigla",
            "SG_UF_IES": "uf", "QT_ING": "ingressantes", "QT_MAT": "matriculas",
        }).to_dict(orient="records"))

    @app.route("/api/ingressantes/genero")
    @auth.login_required
    def api_ingressantes_genero():
        df = aplicar_filtros(get_cursos(), get_filters())
        return jsonify([
            {"genero": "Feminino",  "valor": int(df["QT_MAT_FEM"].sum())},
            {"genero": "Masculino", "valor": int(df["QT_MAT_MASC"].sum())},
        ])

    # ─── CONCLUINTES ─────────────────────────────────────────

    @app.route("/dashboard/concluintes")
    @auth.login_required
    @auth.module_required("concluintes")
    def concluintes():
        return render_template("dashboard/concluintes.html", **dash_ctx("concluintes"))

    @app.route("/api/concluintes/area")
    @auth.login_required
    def api_concluintes_area():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_CINE_AREA_GERAL")["QT_CONC"].sum().reset_index()
        r.columns = ["area", "concluintes"]
        return jsonify(r.sort_values("concluintes", ascending=False).head(10).to_dict(orient="records"))

    @app.route("/api/concluintes/regiao")
    @auth.login_required
    def api_concluintes_regiao():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_REGIAO")["QT_CONC"].sum().reset_index()
        r.columns = ["regiao", "concluintes"]
        return jsonify(r.sort_values("concluintes", ascending=False).to_dict(orient="records"))

    @app.route("/api/concluintes/uf")
    @auth.login_required
    def api_concluintes_uf():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("SG_UF")["QT_CONC"].sum().reset_index()
        r.columns = ["uf", "concluintes"]
        return jsonify(r.sort_values("concluintes", ascending=False).to_dict(orient="records"))

    @app.route("/api/concluintes/modalidade")
    @auth.login_required
    def api_concluintes_modalidade():
        df  = aplicar_filtros(get_cursos(), get_filters())
        MAP = {"1": "Presencial", "2": "EAD", "3": "Semi-presencial"}
        r   = df.groupby("TP_MODALIDADE_ENSINO")["QT_CONC"].sum().reset_index()
        r["modalidade"] = r["TP_MODALIDADE_ENSINO"].astype(str).map(MAP).fillna("Outro")
        r = r[["modalidade", "QT_CONC"]].rename(columns={"QT_CONC": "concluintes"})
        return jsonify(r.sort_values("concluintes", ascending=False).to_dict(orient="records"))

    @app.route("/api/concluintes/cursos_top")
    @auth.login_required
    def api_concluintes_cursos_top():
        df    = aplicar_filtros(get_cursos(), get_filters())
        r     = df.groupby("NO_CURSO")[["QT_CONC", "QT_MAT"]].sum().reset_index()
        r     = r.sort_values("QT_CONC", ascending=False).head(15)
        total = r["QT_CONC"].sum() or 1
        r["market_share"] = (r["QT_CONC"] / total * 100).round(2)
        return jsonify(r.rename(columns={
            "NO_CURSO": "curso", "QT_CONC": "concluintes", "QT_MAT": "matriculas",
        }).to_dict(orient="records"))

    @app.route("/api/concluintes/ies_top")
    @auth.login_required
    def api_concluintes_ies_top():
        df    = aplicar_filtros(get_cursos(), get_filters())
        ies_d = get_ies()[["CO_IES", "NO_IES", "SG_IES", "SG_UF_IES"]].copy()
        ies_d["CO_IES"] = ies_d["CO_IES"].astype(str)
        r = df.groupby("CO_IES")[["QT_CONC", "QT_MAT"]].sum().reset_index()
        r = r.merge(ies_d, on="CO_IES", how="left").sort_values("QT_CONC", ascending=False).head(15)
        total = r["QT_CONC"].sum() or 1
        r["market_share"] = (r["QT_CONC"] / total * 100).round(2)
        return jsonify(r.rename(columns={
            "CO_IES": "co_ies", "NO_IES": "ies", "SG_IES": "sigla",
            "SG_UF_IES": "uf", "QT_CONC": "concluintes", "QT_MAT": "matriculas",
        }).to_dict(orient="records"))

    @app.route("/api/concluintes/genero")
    @auth.login_required
    def api_concluintes_genero():
        df = aplicar_filtros(get_cursos(), get_filters())
        return jsonify([
            {"genero": "Feminino",  "valor": int(df["QT_MAT_FEM"].sum())},
            {"genero": "Masculino", "valor": int(df["QT_MAT_MASC"].sum())},
        ])

    # ─── EVOLUÇÃO CENSAL (2020-2024) ─────────────────────────

    @app.route("/api/censo/evolucao")
    @auth.login_required
    def api_censo_evolucao():
        """
        Retorna evolução anual de matrículas, ingressantes e concluintes.
        Respeita os mesmos filtros das outras abas.
        Parâmetro extra: metrica = 'matriculas' | 'ingressantes' | 'concluintes' | 'todas'
        """
        params  = get_filters()
        metrica = request.args.get("metrica", "todas")
        df      = aplicar_filtros(get_evolucao(), params)

        if df.empty:
            return jsonify([])

        agg = (
            df.groupby("NU_ANO_CENSO")[["QT_MAT", "QT_ING", "QT_CONC"]]
            .sum()
            .reset_index()
            .sort_values("NU_ANO_CENSO")
        )

        col_map = {
            "matriculas":   "QT_MAT",
            "ingressantes": "QT_ING",
            "concluintes":  "QT_CONC",
        }

        if metrica in col_map:
            col = col_map[metrica]
            return jsonify([
                {"ano": r["NU_ANO_CENSO"], "valor": int(r[col])}
                for _, r in agg.iterrows()
            ])

        # metrica == "todas" — retorna as três séries
        return jsonify([
            {
                "ano":         r["NU_ANO_CENSO"],
                "matriculas":  int(r["QT_MAT"]),
                "ingressantes":int(r["QT_ING"]),
                "concluintes": int(r["QT_CONC"]),
            }
            for _, r in agg.iterrows()
        ])

    @app.route("/api/censo/evolucao/modalidade")
    @auth.login_required
    def api_censo_evolucao_modalidade():
        """
        Retorna evolução anual separada por modalidade (Presencial e EAD).
        Parâmetro extra: metrica = 'matriculas' | 'ingressantes' | 'concluintes'
        """
        params  = get_filters()
        metrica = request.args.get("metrica", "matriculas")
        df      = aplicar_filtros(get_evolucao(), params)

        if df.empty:
            return jsonify([])

        col_map = {
            "matriculas":   "QT_MAT",
            "ingressantes": "QT_ING",
            "concluintes":  "QT_CONC",
        }
        col = col_map.get(metrica, "QT_MAT")

        MAP = {"1": "Presencial", "2": "EAD"}
        df  = df[df["TP_MODALIDADE_ENSINO"].isin(["1", "2"])].copy()
        df["MODALIDADE_LABEL"] = df["TP_MODALIDADE_ENSINO"].map(MAP)

        agg = (
            df.groupby(["NU_ANO_CENSO", "MODALIDADE_LABEL"])[col]
            .sum()
            .reset_index()
            .sort_values("NU_ANO_CENSO")
        )

        anos       = sorted(agg["NU_ANO_CENSO"].unique().tolist())
        modalidades = ["Presencial", "EAD"]

        series = []
        for mod in modalidades:
            subset = agg[agg["MODALIDADE_LABEL"] == mod].set_index("NU_ANO_CENSO")
            series.append({
                "modalidade": mod,
                "dados": [
                    {"ano": a, "valor": int(subset.loc[a, col]) if a in subset.index else 0}
                    for a in anos
                ]
            })

        return jsonify(series)

    # ─── FUNIL ───────────────────────────────────────────────

    @app.route("/dashboard/funil")
    @auth.login_required
    @auth.module_required("funil")
    def funil():
        return render_template("dashboard/funil.html", **dash_ctx("funil"))

    @app.route("/api/funil/data")
    @auth.login_required
    def api_funil_data():
        df = aplicar_filtros(get_cursos(), get_filters())
        return jsonify([
            {"etapa": "Vagas",        "valor": int(df["QT_VG_TOTAL"].sum())},
            {"etapa": "Ingressantes", "valor": int(df["QT_ING"].sum())},
            {"etapa": "Matrículas",   "valor": int(df["QT_MAT"].sum())},
            {"etapa": "Concluintes",  "valor": int(df["QT_CONC"].sum())},
        ])

    # ─── CURSOS ──────────────────────────────────────────────

    @app.route("/dashboard/cursos")
    @auth.login_required
    @auth.module_required("cursos")
    def cursos():
        return render_template("dashboard/cursos.html", **dash_ctx("cursos"))

    @app.route("/api/cursos/area")
    @auth.login_required
    def api_cursos_area():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_CINE_AREA_GERAL")["QT_MAT"].sum().reset_index()
        r.columns = ["area", "matriculas"]
        return jsonify(r.sort_values("matriculas", ascending=False).head(10).to_dict(orient="records"))

    @app.route("/api/cursos/top")
    @auth.login_required
    def api_cursos_top():
        df = aplicar_filtros(get_cursos(), get_filters())
        r  = df.groupby("NO_CURSO")[["QT_MAT","QT_ING","QT_CONC","QT_VG_TOTAL"]].sum().reset_index()
        r  = r.sort_values("QT_MAT", ascending=False).head(15)
        total = r["QT_MAT"].sum() or 1
        r["market_share"] = (r["QT_MAT"] / total * 100).round(2)
        return jsonify(r.rename(columns={
            "NO_CURSO": "curso", "QT_MAT": "matriculas",
            "QT_ING": "ingressantes", "QT_CONC": "concluintes", "QT_VG_TOTAL": "vagas",
        }).to_dict(orient="records"))

    # ─── IES ─────────────────────────────────────────────────

    @app.route("/dashboard/ies")
    @auth.login_required
    @auth.module_required("ies")
    def ies():
        return render_template("dashboard/ies.html", **dash_ctx("ies"))

    @app.route("/api/ies/top")
    @auth.login_required
    def api_ies_top():
        df  = aplicar_filtros(get_cursos(), get_filters())
        ies_d = get_ies()[["CO_IES","NO_IES","SG_IES","SG_UF_IES","TP_ORGANIZACAO_ACADEMICA"]].copy()
        ies_d["CO_IES"] = ies_d["CO_IES"].astype(str)
        r   = df.groupby("CO_IES")[["QT_MAT","QT_ING","QT_CONC"]].sum().reset_index()
        r   = r.merge(ies_d, on="CO_IES", how="left").sort_values("QT_MAT", ascending=False).head(15)
        total = r["QT_MAT"].sum() or 1
        r["market_share"] = (r["QT_MAT"] / total * 100).round(2)
        return jsonify(r.rename(columns={
            "CO_IES":"co_ies","QT_MAT":"matriculas","QT_ING":"ingressantes",
            "QT_CONC":"concluintes","NO_IES":"ies","SG_IES":"sigla",
            "SG_UF_IES":"uf","TP_ORGANIZACAO_ACADEMICA":"org",
        }).to_dict(orient="records"))

    # ─── VERSUS ──────────────────────────────────────────────

    @app.route("/dashboard/versus")
    @auth.login_required
    @auth.module_required("versus")
    def versus():
        return render_template("dashboard/versus.html", **dash_ctx("versus"))

    # ─── ADMIN ───────────────────────────────────────────────

    @app.route("/admin/users")
    @auth.admin_required
    def admin_users():
        user = auth.get_current_user()
        ctx = {"current_user": user, "allowed_modules": config.MODULOS, "active_module": "admin"}
        try:
            res  = config.supabase.table("users_conteudo_dash").select("*").order("created_at", desc=True).execute()
            rows = res.data or []
        except Exception as e:
            rows = []
            flash(f"Erro ao buscar usuários: {e}", "error")
        return render_template("admin/users.html", users=rows, **ctx)

    @app.route("/admin/users/novo", methods=["GET", "POST"])
    @auth.admin_required
    def admin_user_new():
        user = auth.get_current_user()
        ctx = {"current_user": user, "allowed_modules": config.MODULOS, "active_module": "admin"}
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email    = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            role     = request.form.get("role", "viewer")
            modulos  = request.form.getlist("modulos")
            if not username or not password:
                flash("Usuário e senha são obrigatórios.", "error")
                return render_template("admin/user_form.html", action="novo", modulos=config.MODULOS, **ctx)
            try:
                res = config.supabase.table("users_conteudo_dash").insert({
                    "username": username, "email": email,
                    "password_hash": auth.hash_password(password),
                    "role": role, "ativo": "true",
                }).execute()
                user_id = str(res.data[0]["id"])
                if role == "viewer" and modulos:
                    rows = [{"user_id": user_id, "modulo": m} for m in modulos]
                    config.supabase.table("user_modules_conteudo_dash").insert(rows).execute()
                flash("Usuário criado com sucesso.", "ok")
                return redirect(url_for("admin_users"))
            except Exception as e:
                flash(f"Erro ao criar usuário: {e}", "error")
        return render_template("admin/user_form.html", action="novo", modulos=config.MODULOS, **ctx)

    @app.route("/admin/users/<int:user_id>", methods=["GET", "POST"])
    @auth.admin_required
    def admin_user_edit(user_id):
        current = auth.get_current_user()
        ctx = {"current_user": current, "allowed_modules": config.MODULOS, "active_module": "admin"}
        try:
            res  = config.supabase.table("users_conteudo_dash").select("*").eq("id", user_id).execute()
            user = res.data[0] if res.data else None
        except Exception:
            user = None
        if not user:
            flash("Usuário não encontrado.", "error")
            return redirect(url_for("admin_users"))
        try:
            mres = config.supabase.table("user_modules_conteudo_dash").select("modulo").eq("user_id", str(user_id)).execute()
            user_modulos = [r["modulo"] for r in mres.data]
        except Exception:
            user_modulos = []
        if request.method == "POST":
            action = request.form.get("action")
            if action == "toggle_ativo":
                novo = "false" if user["ativo"] == "true" else "true"
                config.supabase.table("users_conteudo_dash").update({"ativo": novo}).eq("id", user_id).execute()
                flash("Status atualizado.", "ok")
                return redirect(url_for("admin_user_edit", user_id=user_id))
            if action == "save":
                role    = request.form.get("role", user["role"])
                modulos = request.form.getlist("modulos")
                config.supabase.table("users_conteudo_dash").update({"role": role}).eq("id", user_id).execute()
                config.supabase.table("user_modules_conteudo_dash").delete().eq("user_id", str(user_id)).execute()
                if role == "viewer" and modulos:
                    rows = [{"user_id": str(user_id), "modulo": m} for m in modulos]
                    config.supabase.table("user_modules_conteudo_dash").insert(rows).execute()
                flash("Usuário atualizado.", "ok")
                return redirect(url_for("admin_users"))
            if action == "reset_password":
                new_pw = request.form.get("new_password", "")
                if new_pw:
                    config.supabase.table("users_conteudo_dash").update(
                        {"password_hash": auth.hash_password(new_pw)}
                    ).eq("id", user_id).execute()
                    flash("Senha redefinida.", "ok")
                return redirect(url_for("admin_user_edit", user_id=user_id))
        return render_template("admin/user_form.html",
            action="edit", edit_user=user,
            user_modulos=user_modulos,
            modulos=config.MODULOS, **ctx)

    # ─── ERROS ───────────────────────────────────────────────

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    # ─── DATA LOADER ─────────────────────────────────────────

    start_loader()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)