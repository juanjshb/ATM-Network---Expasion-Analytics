let
    Source = PostgreSQL.Database("192.168.1.50:5432", "atm_network"),
    Locations = Source{[Schema="public", Item="v_atm_locations_powerbi"]}[Data],
    Kpis = Source{[Schema="public", Item="v_atm_kpis_powerbi"]}[Data],
    Runs = Source{[Schema="public", Item="v_scrape_runs_powerbi"]}[Data]
in
    Locations

