pipeline {
  agent any
  stages {
    stage('Build') {
      parallel {
        stage('Service Lifecycle Manager') {
          steps {
            echo 'Building Service Lifecycle Manager container'
            sh './pipeline/build/servicelifecyclemanagement.sh'
          }
        }
        stage('Function Lifecycle Manager') {
          steps {
            echo 'Building Function Lifecycle Manager container'
            sh './pipeline/build/functionlifecyclemanagement.sh'
          }
        }
        stage('Plugin Manager') {
          steps {
            echo 'Building Plugin Manager container'
            sh './pipeline/build/pluginmanager.sh'
          }
        }
        stage('sonmanobase') {
          steps {
            echo 'Building sonmanobase container'
            sh './pipeline/build/sonmanobase.sh'
          }
        }
        stage('Specifc Manager Registry') {
          steps {
            echo 'Building Specific Manager Registry container'
            sh './pipeline/build/specificmanagerregistry.sh'
          }
        }
        stage('Placement Executive') {
          steps {
            echo 'Building Placement Executive container'
            sh './pipeline/build/placementexecutive.sh'
          }
        }
        stage('Placement Plugin') {
          steps {
            echo 'Building Placement Plugin container'
            sh './pipeline/build/placementplugin.sh'
          }
        }
      }
    }
    stage('Unittest Dependencies') {
      steps {
        sh './pipeline/unittest/create_dependencies.sh'
      }
    }
    stage('Unittest Plugin Manager') {
      steps {
        sh './pipeline/unittest/pluginmanager_unittest.sh'
      }
    }
    stage('Uniittest next dependencies') {
      steps {
        sh './pipeline/unittest/create_pm_dependency.sh'
      }
    }
    stage('Unittest Specifc Manager Registry') {
      steps {
        sh './pipeline/unittest/specificmanagerregistry_unittest.sh'
      }
    }
    stage('Unittest second phase'){
      parallel {
        stage('Unittest Service Lifecycle Manager') {
          steps {
            sh './pipeline/unittest/servicelifecyclemanager_unittest.sh'
          }
        }
        stage('Unittest Function Lifecycle Manager') {
          steps {
            sh './pipeline/unittest/functionlifecyclemanager_unittest.sh'
          }
        }
        stage('Unittest sonmanobase') {
          steps {
            sh './pipeline/unittest/sonmanobase_unittest.sh'
          }
        }
        stage('Unittest Placement Executive') {
          steps {
            sh './pipeline/unittest/placementexecutive_unittest.sh'
          }
        }
        stage('Unittest Placement Plugin') {
          steps {
            sh './pipeline/unittest/placementplugin_unittest.sh'
          }
        }
      }
    }
    stage('Checkstyle') {
      parallel {
        stage('Service Lifecycle Manager') {
          steps {
            sh './pipeline/checkstyle/servicelifecyclemanager_stylecheck.sh || true'
          }
        }
        stage('Function Lifecycle Manager') {
          steps {
            sh './pipeline/checkstyle/functionlifecyclemanager_stylecheck.sh || true'
          }
        }
        stage('Plugin Manager') {
          steps {
            sh './pipeline/checkstyle/pluginmanager_stylecheck.sh || true'
          }
        }
        stage('sonmanobase') {
          steps {
            sh './pipeline/checkstyle/sonmanobase_stylecheck.sh || true'
          }
        }
        stage('Specifc Manager Registry') {
          steps {
            sh './pipeline/checkstyle/specificmanagerregistry_stylecheck.sh || true'
          }
        }
        stage('Placement Executive') {
          steps {
            sh './pipeline/checkstyle/placementexecutive_stylecheck.sh || true'
          }
        }
        stage('Placement Plugin') {
          steps {
            sh './pipeline/checkstyle/placementplugin_stylecheck.sh || true'
          }
        }
      }
    }
    stage('Publish to :latest') {
      parallel {
        stage('Service Lifecycle Manager') {
          steps {
            echo 'Publishing Service Lifecycle Manager container'
            sh './pipeline/publish/servicelifecyclemanagement.sh latest'
          }
        }
        stage('Function Lifecycle Manager') {
          steps {
            echo 'Publishing Function Lifecycle Manager container'
            sh './pipeline/publish/functionlifecyclemanagement.sh latest'
          }
        }
        stage('Plugin Manager') {
          steps {
            echo 'Publishing Plugin Manager container'
            sh './pipeline/publish/pluginmanager.sh latest'
          }
        }
        stage('sonmanobase') {
          steps {
            echo 'Publishing sonmanobase container'
            sh './pipeline/publish/sonmanobase.sh latest'
          }
        }
        stage('Specifc Manager Registry') {
          steps {
            echo 'Publishing Specific Manager Registry container'
            sh './pipeline/publish/specificmanagerregistry.sh latest'
          }
        }
        stage('Placement Executive') {
          steps {
            echo 'Publishing Placement Executive container'
            sh './pipeline/publish/placementexecutive.sh latest'
          }
        }
        stage('Placement Plugin') {
          steps {
            echo 'Publishing Placement Plugin container'
            sh './pipeline/publish/placementplugin.sh latest'
          }
        }
      }
    }
    stage('Deploying in pre-integration ') {
      when{
        not{
          branch 'master'
        }        
      }      
      steps {
        sh 'rm -rf tng-devops || true'
        sh 'git clone https://github.com/sonata-nfv/tng-devops.git'
        dir(path: 'tng-devops') {
          sh 'ansible-playbook roles/sp.yml -i environments -e "target=pre-int-sp" component=mano-framework"'
        }
      }
    }
    stage('Publishing to :int') {
      when{
        branch 'master'
      }      
      parallel {
        stage('Service Lifecycle Manager') {
          steps {
            echo 'Publishing Service Lifecycle Manager container'
            sh './pipeline/publish/servicelifecyclemanagement.sh int'
          }
        }
        stage('Function Lifecycle Manager') {
          steps {
            echo 'Publishing Function Lifecycle Manager container'
            sh './pipeline/publish/functionlifecyclemanagement.sh int'
          }
        }
        stage('Plugin Manager') {
          steps {
            echo 'Publishing Plugin Manager container'
            sh './pipeline/publish/pluginmanager.sh int'
          }
        }
        stage('sonmanobase') {
          steps {
            echo 'Publishing sonmanobase container'
            sh './pipeline/publish/sonmanobase.sh int'
          }
        }
        stage('Specifc Manager Registry') {
          steps {
            echo 'Publishing Specific Manager Registry container'
            sh './pipeline/publish/specificmanagerregistry.sh int'
          }
        }
        stage('Placement Executive') {
          steps {
            echo 'Publishing Placement Executive container'
            sh './pipeline/publish/placementexecutive.sh int'
          }
        }
        stage('Placement Plugin') {
          steps {
            echo 'Publishing Placement Plugin container'
            sh './pipeline/publish/placementplugin.sh int'
          }
        }
      }
    }
    stage('Deploying in integration') {
      when{
        branch 'master'
      }      
      steps {
        sh './pipeline/publish/retag.sh'
        sh 'rm -rf tng-devops || true'
        sh 'git clone https://github.com/sonata-nfv/tng-devops.git'
        dir(path: 'tng-devops') {
          sh 'ansible-playbook roles/sp.yml -i environments -e "target=int-sp" component=mano-framework"'
        }
      }
    }
  }
  post {
    always {
      echo 'Clean Up'
      sh './pipeline/cleanup/clean_environment.sh'
    }
    success {
        emailext (
          subject: "SUCCESS: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
          body: """<p>SUCCESS: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
            <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
        recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
      }
    failure {
      emailext (
          subject: "FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
          body: """<p>FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
            <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
          recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
    }  
  }
}
