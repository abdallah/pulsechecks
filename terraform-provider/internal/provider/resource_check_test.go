package provider

import (
	"fmt"
	"testing"

	"github.com/hashicorp/terraform-plugin-testing/helper/resource"
)

func TestAccCheckResource(t *testing.T) {
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) },
		ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
		Steps: []resource.TestStep{
			{
				Config: testAccCheckResourceConfig("test-check"),
				Check: resource.ComposeAggregateTestCheckFunc(
					resource.TestCheckResourceAttr("pulsechecks_check.test", "name", "test-check"),
					resource.TestCheckResourceAttr("pulsechecks_check.test", "period_seconds", "3600"),
					resource.TestCheckResourceAttr("pulsechecks_check.test", "grace_seconds", "300"),
					resource.TestCheckResourceAttrSet("pulsechecks_check.test", "check_id"),
					resource.TestCheckResourceAttrSet("pulsechecks_check.test", "token"),
				),
			},
		},
	})
}

func testAccCheckResourceConfig(name string) string {
	return fmt.Sprintf(`
%s

resource "pulsechecks_team" "test" {
  name = "test-team"
}

resource "pulsechecks_check" "test" {
  team_id        = pulsechecks_team.test.team_id
  name           = %[2]q
  period_seconds = 3600
  grace_seconds  = 300
}
`, providerConfig, name)
}
