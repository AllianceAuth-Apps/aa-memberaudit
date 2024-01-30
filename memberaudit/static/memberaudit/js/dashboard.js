/** Functionality for dashboard panel. */

"use strict";

/* Fetch player count from endpoint and update DOM element. */
window.addEventListener("DOMContentLoaded", () => {
    const elemPlayerCount = document.getElementById("dashboard-player-count");

    fetch(elemPlayerCount.dataset.url)
        .then((response) => {
            if (response.ok) {
                return response.json();
            }
            throw new Error("Something went wrong");
        })
        .then((responseJson) => {
            const playerCount = responseJson.player_count;
            if (playerCount == null) {
                elemPlayerCount.textContent = "?";
            } else {
                elemPlayerCount.textContent = playerCount.toLocaleString();
            }
        })
        .catch((error) => {
            console.log(error);
            elemPlayerCount.textContent = "ERROR";
        });
});
