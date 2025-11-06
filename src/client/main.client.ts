import { CreateClient } from "shared/tver/exports";
import { SpeedBoost, Stun } from "shared/tver/test/compound_effects_classes";

const client = CreateClient()
client.Start()
new SpeedBoost(2).Destroy()
