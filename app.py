"""
LevelOutside — Streamlit app.

Run from the repo root:
    .venv\\Scripts\\python.exe -m streamlit run app.py
"""
from __future__ import annotations


def main() -> None:
    import streamlit as st

    from leveloutside import (
        MissionContext,
        generate_with_retries,
        safe_fallback,
    )
    from leveloutside.card import render_card
    from leveloutside.games import (
        get_profile,
        list_titles,
        profile_from_description,
    )
    from leveloutside.llm import make_generator

    st.set_page_config(page_title="LevelOutside", page_icon="\U0001f333")
    st.title("\U0001f333 LevelOutside")
    st.caption("Turn a favourite game into a real-life outdoor mission — printed on paper.")

    # ── Inanimate-only object choices ────────────────────────────────
    OBJECT_CHOICES = [
        "tree", "stick", "stone", "bench", "leaf", "grass", "flower",
        "bush", "sand", "path", "fence", "wall", "slide", "swing",
        "log", "mud", "hill",
    ]

    # ── Step 1: settings ─────────────────────────────────────────────
    st.header("1 \u2014 Settings")

    age_band = st.selectbox("Age band", ["5-7", "8-10", "11-13"], index=1)
    duration = st.selectbox("Minutes outside", [20, 40], index=0)

    titles = list_titles()
    game_options = titles + ["Other (describe it)"]
    game_choice = st.selectbox("Favourite game", game_options)

    profile = None
    if game_choice == "Other (describe it)":
        desc = st.text_input("Describe the game in one sentence")
        if desc:
            try:
                profile = profile_from_description(desc)
            except ValueError as exc:
                st.error(str(exc))
    else:
        profile = get_profile(game_choice)

    # ── Step 2: object checklist ─────────────────────────────────────
    st.header("2 \u2014 What is outside?")
    st.caption("Tick the objects and plants that are actually in the outdoor space. "
               "At least one is required.")
    confirmed = st.multiselect("Confirmed objects", OBJECT_CHOICES)

    # ── Step 3: generate ─────────────────────────────────────────────
    st.header("3 \u2014 Make the mission")

    ready = bool(profile) and len(confirmed) >= 1

    if not ready:
        if not profile:
            st.info("Choose a game (or describe one) above.")
        elif len(confirmed) < 1:
            st.info("Select at least one outdoor object above.")

    col1, col2 = st.columns(2)

    with col1:
        generate_clicked = st.button("\U0001f680 Make my mission",
                                     disabled=not ready, use_container_width=True)
    with col2:
        fallback_clicked = st.button("\u26a1 Use the quick safe mission instead",
                                     disabled=not ready, use_container_width=True)

    if ready and (generate_clicked or fallback_clicked):
        ctx = MissionContext(
            confirmed_objects=set(confirmed),
            age_band=age_band,
            duration_min=duration,
        )
        game_title = profile["title"]

        if fallback_clicked:
            mission = safe_fallback(ctx)
            st.session_state["result"] = {
                "mission": mission,
                "attempts": 0,
                "used_fallback": True,
                "failure_codes": [],
                "ctx": ctx,
                "game_title": game_title,
            }

        else:
            try:
                gen = make_generator(profile, set(confirmed), ctx)
                with st.spinner("Generating your mission \u2014 this can take a couple of minutes\u2026"):
                    result = generate_with_retries(gen, ctx)
                st.session_state["result"] = {
                    "mission": result.mission,
                    "attempts": result.attempts,
                    "used_fallback": result.used_fallback,
                    "failure_codes": result.failure_codes,
                    "ctx": ctx,
                    "game_title": game_title,
                }
            except RuntimeError as exc:
                st.error(
                    f"Could not reach Ollama: {exc}\n\n"
                    "You can use the quick safe mission instead."
                )

    # ── Step 4: display result ───────────────────────────────────────
    r = st.session_state.get("result")
    if r:
        mission = r["mission"]
        ctx = r["ctx"]
        game_title = r["game_title"]

        st.divider()
        st.subheader(mission.title)
        st.write(f"**Attempts:** {r['attempts']}  |  "
                 f"**Fallback used:** {'Yes' if r['used_fallback'] else 'No'}")
        if r["failure_codes"]:
            for i, codes in enumerate(r["failure_codes"], 1):
                st.caption(f"Attempt {i} failure codes: {codes}")

        st.write(f"*{mission.story_hook}*")
        for i, task in enumerate(mission.tasks, 1):
            st.write(f"{i}. **[{task.mechanic}]** {task.instruction} ({task.minutes} min)")
        st.write(f"**Finale:** {mission.finale}")
        st.write(f"\U0001f3c6 Achievement: *{mission.achievement_name}*")

        # ── Download card ────────────────────────────────────────────
        html = render_card(mission, ctx, game_title)
        st.download_button(
            "\U0001f4e5 Download printable card (HTML)",
            data=html,
            file_name="mission_card.html",
            mime="text/html",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
