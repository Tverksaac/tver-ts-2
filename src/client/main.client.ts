import { CreateClient } from "shared/tver";
import { Stun } from "shared/tver/test/compound_effects_classes";

new Stun(true).Destroy();

const client = CreateClient();
client.Start();
