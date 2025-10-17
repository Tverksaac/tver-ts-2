import { Players, Workspace } from "@rbxts/services";
import { SeparatedProperty } from "shared/tver/classes/fundamental/property";
import { ConnectedStat } from "shared/tver/classes/fundamental/stat";
import { Character, CompoundEffectsContainer, CreateServer } from "shared/tver/exports";
const server = CreateServer()
server.Start()
task.wait(8)

const effect = CompoundEffectsContainer.GetCompoundEffectFromName("Stun")
print(effect)
const plr = Players.GetPlayers()[0]
if (plr) {
    const char = plr.Character
    const tver_char = char? new Character(char): undefined
    if (tver_char !== undefined) {
        print(1)
        tver_char.AddStat(new ConnectedStat<Humanoid, "Health">("Health", 10, tver_char.humanoid, "Health"))
        tver_char.AddStat(new ConnectedStat<Humanoid, "NameDisplayDistance">("DisplayNameDistance", 100, tver_char.humanoid, "NameDisplayDistance"))
        tver_char.AddProperty(new SeparatedProperty("Test", 100))
        tver_char.AddProperty(new SeparatedProperty("Test", 100))
    }
}